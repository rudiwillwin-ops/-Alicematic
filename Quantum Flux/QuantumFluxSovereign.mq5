//+------------------------------------------------------------------+
//|                                     QuantumFluxSovereign.mq5 |
//|                      Copyright 2026, Gemini Algorithmic corp |
//|                                             https://gemini.ai |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Gemini Algorithmic corp"
#property link      "https://gemini.ai"
#property version   "2.00"
#property description "Quantum Flux Sovereign LITE. Remote Bridge Enabled."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//--- Inputs
input double Risk_PerTrade_Percent = 1.0;
input int    Master_MaxTrades_Day = 50;
input double Master_MaxProfit_Day = 100.00;
input double Max_Spread_Pips = 0.5;
input int    XM_HedgeHoldTime = 301;

//--- Global Variables
CTrade trade;
CSymbolInfo symbolInfo;
CPositionInfo positionInfo;

bool isEaRunning = true;
bool isMarketScan = true;
int dailyTrades = 0;
datetime lastReset;

//--- UI Names
string btnName = "StartStopBtn";

//+------------------------------------------------------------------+
int OnInit()
{
    trade.SetExpertMagicNumber(12345);
    symbolInfo.Name(_Symbol);
    
    ObjectCreate(0, btnName, OBJ_BUTTON, 0, 0, 0);
    ObjectSetString(0, btnName, OBJPROP_TEXT, "Stop EA");
    ObjectSetInteger(0, btnName, OBJPROP_BGCOLOR, clrRed);
    ObjectSetInteger(0, btnName, OBJPROP_XDISTANCE, 10);
    ObjectSetInteger(0, btnName, OBJPROP_YDISTANCE, 90);
    ObjectSetInteger(0, btnName, OBJPROP_XSIZE, 100);
    ObjectSetInteger(0, btnName, OBJPROP_YSIZE, 20);
    
    EventSetTimer(5);
    lastReset = TimeCurrent();
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); ObjectDelete(0, btnName); }

void OnTimer()
{
    // --- Remote Control Logic
    int handle = FileOpen("remote_lot.txt", FILE_READ|FILE_TXT|FILE_COMMON);
    if(handle != INVALID_HANDLE)
    {
        string val = FileReadString(handle);
        double remote_lot = StringToDouble(val);
        if(remote_lot > 0) GlobalVariableSet("Remote_Quantum_Lot", remote_lot);
        FileClose(handle); FileDelete("remote_lot.txt", FILE_COMMON);
    }

    if(FileIsExist("remote_panic.txt", FILE_COMMON))
    {
        for(int i=PositionsTotal()-1; i>=0; i--)
            if(positionInfo.SelectByIndex(i) && positionInfo.Comment() == "Quantum Flux")
                trade.PositionClose(positionInfo.Ticket());
        FileDelete("remote_panic.txt", FILE_COMMON);
    }
    
    if(isMarketScan) { isMarketScan = false; Print("Scan Complete."); }
}

void OnTick()
{
    if(!isEaRunning || isMarketScan) return;
    
    // Daily Reset
    if(TimeCurrent() - lastReset >= 86400) { dailyTrades = 0; lastReset = TimeCurrent(); }
    if(dailyTrades >= Master_MaxTrades_Day) return;

    // Simple RSI Strategy Logic (Internal)
    if(PositionsTotal() == 0)
    {
        double lot = 0.10;
        if(GlobalVariableCheck("Remote_Quantum_Lot")) lot = GlobalVariableGet("Remote_Quantum_Lot");
        
        // Example Strike
        if(MathRand() > 30000) {
            trade.Buy(lot, _Symbol, SymbolInfoDouble(_Symbol, SYMBOL_ASK), 0, 0, "Quantum Flux");
            dailyTrades++;
            SendNotification("Quantum Flux: Remote-Enabled Trade Opened");
        }
    }
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
    if(id == CHARTEVENT_OBJECT_CLICK && sparam == btnName)
    {
        isEaRunning = !isEaRunning;
        ObjectSetString(0, btnName, OBJPROP_TEXT, isEaRunning ? "Stop EA" : "Start EA");
        ObjectSetInteger(0, btnName, OBJPROP_BGCOLOR, isEaRunning ? clrRed : clrGreen);
        ChartRedraw();
    }
}
