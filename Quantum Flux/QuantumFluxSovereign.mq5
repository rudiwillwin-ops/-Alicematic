//+------------------------------------------------------------------+
//|                                     QuantumFluxSovereign.mq5 |
//|                      Copyright 2026, Gemini Algorithmic corp |
//|                                             https://gemini.ai |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Gemini Algorithmic corp"
#property link      "https://gemini.ai"
#property version   "1.00"
#property description "Quantum Flux Sovereign EA. Implements Quiet Volatile, Black Swan, and Volatile Rebate strategies."

//--- Include necessary libraries
#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>
#include <Math/Stat/StdDev.mqh>

//--- Input Parameters ---

//--- Strategy: Quiet Volatile (Rebate Churn)
input group "Quiet Volatile Strategy"
input double QuietVolatile_PipTarget = 1.5;         // Target profit in pips
input int    QuietVolatile_MaxTrades = 100;         // Max trades per day

//--- Strategy: Black Swan (Crisis Mode)
input group "Black Swan Strategy"
input double BlackSwan_ActivationProfit = 15.0;     // Minimum profit to activate
input int    BlackSwan_AtrPeriod = 14;              // ATR period for volatility
input double BlackSwan_AtrMultiplier = 3.0;         // ATR multiplier for SD moves

//--- Strategy: Volatile Rebate (News Scalping)
input group "Volatile Rebate Strategy"
input int    VolatileRebate_BbPeriod = 20;          // Bollinger Bands period
input double VolatileRebate_BbDeviations = 2.0;     // Bollinger Bands deviations

//--- Broker Specific: XM Hedge Logic
input group "XM Hedge Logic"
input int    XM_HedgeHoldTime = 301;                // Hold time in seconds (5m 1s)

//--- Risk & Safety
input group "Risk & Safety Management"
input double Risk_PerTrade_Percent = 1.0;           // Risk percentage per trade
input int    Master_MaxTrades_Day = 50;             // Max successful trades per day
input double Master_MaxProfit_Day = 100.00;         // Max daily profit
input double Max_Spread_Pips = 0.5;                 // Maximum allowed spread in pips

//--- UI & UX
input group "UI & UX Settings"
input bool   Enable_Sounds = true;                  // Enable sound alerts

//--- Global Variables ---
CTrade trade;
CSymbolInfo symbolInfo;
CPositionInfo positionInfo;

//--- Strategy state
bool isBlackSwanActive = false;
bool isMarketScanPhase = true;
bool isEaRunning = true; // EA is running by default

//--- Daily counters
int dailyTradeCounter = 0;
double dailyProfit = 0.0;
datetime lastResetTime;

//--- UI Object Names
string accountBadgeName = "AccountBadge";
string rebateTickerName = "RebateTicker";
string blackSwanLightName = "BlackSwanLight";
string hedgeTimerName = "HedgeTimer";
string startStopButtonName = "StartStopButton";

//--- Custom Hedging Class ---
class CHedgeManager
{
private:
    long              m_original_ticket;
    long              m_hedge_ticket;
    datetime          m_hedge_time;
    CTrade           *m_trade;

public:
    void              CHedgeManager(void) : m_original_ticket(0), m_hedge_ticket(0), m_hedge_time(0) {}
    void              Init(CTrade &trade_object) { m_trade = &trade_object; }

    bool              IsHedgeActive(void) const { return m_original_ticket != 0 && m_hedge_ticket != 0; }
    datetime          GetHedgeTime(void) const { return m_hedge_time; }

    bool              StartHedge(long ticket)
    {
        if(!positionInfo.SelectByTicket(ticket)) return false;
        
        m_original_ticket = ticket;
        double volume = positionInfo.Volume();
        string symbol = positionInfo.Symbol();
        ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)positionInfo.PositionType();

        ENUM_ORDER_TYPE hedge_order_type = (type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
if(!m_trade.PositionOpen(symbol, hedge_order_type, volume, 
                        (hedge_order_type == ORDER_TYPE_SELL) ? symbolInfo.Ask() : symbolInfo.Bid(), 
                        0, 0, "Quantum Flux"))
{
    m_original_ticket = 0;
    return false;
}
SendNotification("Quantum Flux: Hedge opened on " + symbol);
return true;
        m_hedge_ticket = m_trade.ResultDeal();
        m_hedge_time = TimeCurrent();
        return true;
    }

    void              CloseHedgePositions(void)
    {
        if(!IsHedgeActive()) return;

        if(positionInfo.SelectByTicket(m_original_ticket))
        {
            m_trade.PositionClose(m_original_ticket);
        }

        if(positionInfo.SelectByTicket(m_hedge_ticket))
        {
            m_trade.PositionClose(m_hedge_ticket);
        }
        
        // Reset state
        m_original_ticket = 0;
        m_hedge_ticket = 0;
        m_hedge_time = 0;
    }
};

CHedgeManager hedgeManager;

//--- Expert Advisor Main Functions ---
int OnInit();
void OnDeinit(const int reason);
void OnTick();
void OnTimer();
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam);

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    //--- Initialize trade object
    trade.SetExpertMagicNumber(12345);
    trade.SetDeviationInPoints(10);
    trade.SetTypeFilling(ORDER_FILLING_FOK);
    symbolInfo.Name(_Symbol);
    hedgeManager.Init(trade);

    //--- Create UI Dashboard ---
    // Account Badge
    ObjectCreate(0, accountBadgeName, OBJ_LABEL, 0, 0, 0);
    ObjectSetString(0, accountBadgeName, OBJPROP_TEXT, "ACCOUNT: " + (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "LIVE"));
    ObjectSetInteger(0, accountBadgeName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, accountBadgeName, OBJPROP_YDISTANCE, 10);

    // Rebate Pulse Ticker
    ObjectCreate(0, rebateTickerName, OBJ_LABEL, 0, 0, 0);
    ObjectSetString(0, rebateTickerName, OBJPROP_TEXT, "REBATE PULSE: STANDBY");
    ObjectSetInteger(0, rebateTickerName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, rebateTickerName, OBJPROP_YDISTANCE, 30);

    // Black Swan Standby Light
    ObjectCreate(0, blackSwanLightName, OBJ_LABEL, 0, 0, 0);
    ObjectSetString(0, blackSwanLightName, OBJPROP_TEXT, "BLACK SWAN: INACTIVE");
    ObjectSetInteger(0, blackSwanLightName, OBJPROP_COLOR, clrRed);
    ObjectSetInteger(0, blackSwanLightName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, blackSwanLightName, OBJPROP_YDISTANCE, 50);

    // XM Hedge Timer
    ObjectCreate(0, hedgeTimerName, OBJ_LABEL, 0, 0, 0);
    ObjectSetString(0, hedgeTimerName, OBJPROP_TEXT, "HEDGE TIMER: --:--");
    ObjectSetInteger(0, hedgeTimerName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, hedgeTimerName, OBJPROP_YDISTANCE, 70);

    //--- Start/Stop Button ---
    ObjectCreate(0, startStopButtonName, OBJ_BUTTON, 0, 0, 0);
    ObjectSetString(0, startStopButtonName, OBJPROP_TEXT, "Stop EA");
    ObjectSetInteger(0, startStopButtonName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_YDISTANCE, 90);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_XSIZE, 100);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_YSIZE, 20);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_BGCOLOR, clrRed);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_COLOR, clrWhite);
    ObjectSetInteger(0, startStopButtonName, OBJPROP_STATE, false);


    //--- Tell terminal we want to receive chart events
    ChartSetInteger(0, CHART_EVENT_OBJECT_CLICK, true);

    //--- Startup Market Scan ---
    Print("Quantum Flux Sovereign: Starting 5-minute market scan.");
    EventSetTimer(300); // 5 minutes * 60 seconds

    lastResetTime = TimeCurrent();

    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    //--- Kill timers
    EventKillTimer();

    //--- Remove UI Objects
    ObjectDelete(0, accountBadgeName);
    ObjectDelete(0, rebateTickerName);
    ObjectDelete(0, blackSwanLightName);
    ObjectDelete(0, hedgeTimerName);
    ObjectDelete(0, startStopButtonName);
    
    Print("Quantum Flux Sovereign: Deinitialized.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    //--- Check if EA is allowed to run
    if(!isEaRunning)
        return;

    //--- Wait for market scan to complete
    if(isMarketScanPhase)
        return;

    //--- Daily Reset
    if(TimeCurrent() - lastResetTime >= 86400)
    {
        dailyTradeCounter = 0;
        dailyProfit = 0;
        lastResetTime = TimeCurrent();
        Print("Quantum Flux Sovereign: Daily counters reset.");
    }
    
    //--- Master Kill-Switch ---
    if(dailyTradeCounter >= Master_MaxTrades_Day || dailyProfit >= Master_MaxProfit_Day)
    {
        if(PositionsTotal() > 0)
        {
            // Close all positions
            for(int i = PositionsTotal() - 1; i >= 0; i--)
            {
                if(positionInfo.SelectByIndex(i) && positionInfo.Symbol() == _Symbol && positionInfo.Magic() == trade.ExpertMagicNumber())
                {
                    trade.PositionClose(positionInfo.Ticket());
                }
            }
        }
        ObjectSetString(0, rebateTickerName, OBJPROP_TEXT, "DAILY LIMIT REACHED");
        return; // Stop all further processing
    }

    //--- Spread Validator ---
    symbolInfo.RefreshRates();
    double spread = (symbolInfo.Ask() - symbolInfo.Bid()) / _Point;
    if(spread > Max_Spread_Pips)
    {
        ObjectSetString(0, rebateTickerName, OBJPROP_TEXT, "SPREAD TOO HIGH");
        return;
    }
    else
    {
        ObjectSetString(0, rebateTickerName, OBJPROP_TEXT, "REBATE PULSE: ACTIVE");
    }

    //--- Hedge Management ---
    if(hedgeManager.IsHedgeActive())
    {
        if(TimeCurrent() - hedgeManager.GetHedgeTime() >= XM_HedgeHoldTime)
        {
            hedgeManager.CloseHedgePositions();
            dailyTradeCounter++; // Count it as one successful trade
            // dailyProfit will be calculated from history
        }
        return; // Don't do anything else while hedge is active
    }

    //--- Main Logic ---
    if(PositionsTotal() == 0)
    {
        //--- No positions are open, look for a new trade
        
        // Strategy 1: Black Swan (Highest Priority)
        if(ExecuteBlackSwan()) return;
        
        // Strategy 2: Volatile Rebate
        if(ExecuteVolatileRebate()) return;
        
        // Strategy 3: Quiet Volatile (Default)
        ExecuteQuietVolatile();
    }
    else if (PositionsTotal() == 1)
    {
        //--- One position is open, manage it
        if(positionInfo.SelectByIndex(0) && positionInfo.Symbol() == _Symbol && positionInfo.Magic() == trade.ExpertMagicNumber())
        {
            double pips = (positionInfo.PriceCurrent() - positionInfo.PriceOpen()) / _Point;
            if(positionInfo.PositionType() == POSITION_TYPE_SELL) pips *= -1;

            if(pips >= QuietVolatile_PipTarget)
            {
                if(Enable_Sounds) PlaySound("ping.wav");
                hedgeManager.StartHedge(positionInfo.Ticket());
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
    if(isMarketScanPhase)
    {
        isMarketScanPhase = false;
        EventKillTimer();
        Print("Quantum Flux Sovereign: Market scan complete. Trading enabled.");
        // We can set a 1 second timer for UI updates if needed
        EventSetTimer(1);
    }

    // --- Update Hedge Timer on UI ---
    if(hedgeManager.IsHedgeActive())
    {
        datetime hedgeStartTime = hedgeManager.GetHedgeTime();
        int seconds_passed = TimeCurrent() - hedgeStartTime;
        int seconds_left = XM_HedgeHoldTime - seconds_passed;
        if(seconds_left < 0) seconds_left = 0;
        
        string timer_text = "HEDGE TIMER: " + IntegerToString(seconds_left / 60, 2, '0') + ":" + IntegerToString(seconds_left % 60, 2, '0');
        ObjectSetString(0, hedgeTimerName, OBJPROP_TEXT, timer_text);
    }
    else
    {
        ObjectSetString(0, hedgeTimerName, OBJPROP_TEXT, "HEDGE TIMER: --:--");
    }
}

//+------------------------------------------------------------------+
//| Chart Event function                                             |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
    if(id == CHARTEVENT_OBJECT_CLICK && sparam == startStopButtonName)
    {
        isEaRunning = !isEaRunning; // Toggle the state
        
        if(isEaRunning)
        {
            ObjectSetString(0, startStopButtonName, OBJPROP_TEXT, "Stop EA");
            ObjectSetInteger(0, startStopButtonName, OBJPROP_BGCOLOR, clrRed);
        }
        else
        {
            ObjectSetString(0, startStopButtonName, OBJPROP_TEXT, "Start EA");
            ObjectSetInteger(0, startStopButtonName, OBJPROP_BGCOLOR, clrGreen);
        }
        ChartRedraw();
    }
}

//--- Custom Functions ---

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Risk                                 |
//+------------------------------------------------------------------+
double CalculateLotSize(double stopLossPips)
{
    double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskAmount = accountBalance * (Risk_PerTrade_Percent / 100.0);
    
    // Ensure symbol info is up to date
    symbolInfo.RefreshRates();
    
    double tickValue = symbolInfo.TickValue();
    double tickSize = symbolInfo.TickSize();

    if(tickValue <= 0 || tickSize <= 0) return 0.01; // Fallback

    double sl_in_points = stopLossPips * 10;
    if (Digits() == 3 || Digits() == 5)
    {
        sl_in_points = stopLossPips * pow(10, Digits() - 1);
    }

    double lotSize = riskAmount / (sl_in_points * tickValue);
    
    // Normalize lot size
    double minLot = symbolInfo.LotsMin();
    double maxLot = symbolInfo.LotsMax();
    double lotStep = symbolInfo.LotsStep();
    
    lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
    lotSize = floor(lotSize / lotStep) * lotStep;

    return lotSize;
}

//+------------------------------------------------------------------+
//| Strategy 3: Quiet Volatile (Rebate Churn)                        |
//+------------------------------------------------------------------+
void ExecuteQuietVolatile()
{
    if (dailyTradeCounter >= QuietVolatile_MaxTrades) return;

    // This is a simple momentum strategy for small moves.
    // For this example, we'll just enter a trade randomly and rely on the quick exit.
    // A real implementation would have a more sophisticated entry signal.
    
    double lot = CalculateLotSize(10); // 10 pips SL for calculation
    if(lot <= 0) return;
    
    // Randomly decide buy or sell for demonstration
    if(MathRand() > 16384)
    {
        if(trade.Buy(lot, _Symbol, symbolInfo.Ask(), 0, 0, "Quantum Flux"))
            SendNotification("Quantum Flux: BUY opened on " + _Symbol);
    }
    else
    {
        if(trade.Sell(lot, _Symbol, symbolInfo.Bid(), 0, 0, "Quantum Flux"))
            SendNotification("Quantum Flux: SELL opened on " + _Symbol);
    }
}

//+------------------------------------------------------------------+
//| Strategy 2: Volatile Rebate (BB Touch & Go)                      |
//+------------------------------------------------------------------+
bool ExecuteVolatileRebate()
{
    double bb[3]; // 0: Main, 1: Upper, 2: Lower
    
    for(int i=0; i<3; i++)
    {
        bb[i] = iBands(_Symbol, PERIOD_CURRENT, VolatileRebate_BbPeriod, VolatileRebate_BbDeviations, 0, PRICE_CLOSE, i, 1);
    }

    double upperBand = bb[1];
    double lowerBand = bb[2];
    
    double lot = CalculateLotSize(20); // 20 pips SL for calculation
    if(lot <= 0) return false;

    // Check for "Touch & Go"
    if(symbolInfo.Bid() > upperBand) // Price is above upper band, expect reversal down
    {
        if(trade.Sell(lot, _Symbol, symbolInfo.Bid(), 0, 0, "Quantum Flux"))
        {
            SendNotification("Quantum Flux: SELL (Volatile Rebate) on " + _Symbol);
            return true;
        }
    }
    else if(symbolInfo.Ask() < lowerBand) // Price is below lower band, expect reversal up
    {
        if(trade.Buy(lot, _Symbol, symbolInfo.Ask(), 0, 0, "Quantum Flux"))
        {
            SendNotification("Quantum Flux: BUY (Volatile Rebate) on " + _Symbol);
            return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Strategy 1: Black Swan (ATR Crisis Mode)                         |
//+------------------------------------------------------------------+
bool ExecuteBlackSwan()
{
    // Activate Black Swan mode
    if(!isBlackSwanActive && AccountInfoDouble(ACCOUNT_PROFIT) >= BlackSwan_ActivationProfit)
    {
        isBlackSwanActive = true;
        ObjectSetString(0, blackSwanLightName, OBJPROP_TEXT, "BLACK SWAN: ACTIVE");
        ObjectSetInteger(0, blackSwanLightName, OBJPROP_COLOR, clrGreen);
        if(Enable_Sounds) PlaySound("siren.wav");
    }

    if(!isBlackSwanActive) return false;

    // ATR Calculation
    double atr_val[1];
    if(CopyBuffer(iATR(_Symbol, PERIOD_CURRENT, BlackSwan_AtrPeriod), 0, 1, 1, atr_val) <= 0)
        return false;

    double move_threshold = atr_val[0] * BlackSwan_AtrMultiplier;

    // Price change in last bar
    MqlRates rates[2];
    if(CopyRates(_Symbol, PERIOD_CURRENT, 1, 2, rates) < 2)
        return false;
    
    double price_change = MathAbs(rates[0].open - rates[0].close);

    if(price_change > move_threshold)
    {
        double lot = CalculateLotSize(50); // 50 pips SL for calculation
        if(lot <= 0) return false;
        
        if(rates[0].close > rates[0].open) // Bullish bar
        {
            if(trade.Buy(lot, _Symbol, symbolInfo.Ask(), 0, 0, "Quantum Flux"))
            {
                SendNotification("Quantum Flux: BLACK SWAN BUY on " + _Symbol);
            }
        }
        else // Bearish bar
        {
            if(trade.Sell(lot, _Symbol, symbolInfo.Bid(), 0, 0, "Quantum Flux"))
            {
                SendNotification("Quantum Flux: BLACK SWAN SELL on " + _Symbol);
            }
        }
        return true;
    }

    return false;
}
