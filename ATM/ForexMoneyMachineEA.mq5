//+------------------------------------------------------------------+
//|                                                  ForexMoneyMachineEA.mq5 |
//|                              A professional MQL5 Expert Advisor |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>
#include <ChartObjects/ChartObjectsTxtControls.mqh>
#include <ChartObjects/ChartObjectsTxt.mqh>

//--- Inputs
input double RiskPercent = 2.0;
input int MaxTradesPerPair = 2;
input string BotToken = "";
input long ChatID = 0;

//--- Constants
const int FAST_MA = 10;
const int SLOW_MA = 50;
const ENUM_TIMEFRAMES STRATEGY_TF = PERIOD_H1;
const double SL_PCT = 0.015;   // 1.5%
const double TP_PCT = 0.015;   // 1.5%
const int TIMER_SECONDS = 60;

//--- Symbols to trade
string Symbols[] =
{
   "EURUSD",
   "GBPUSD",
   "USDJPY",
   "AUDUSD",
   "USDCHF"
};

//--- Trading
CTrade trade;
bool botRunning = false;
int lastUpdateId = 0;

//--- UI Objects
CChartObjectButton btnStart;
CChartObjectButton btnStop;
CChartObjectLabel lblStatus;
CChartObjectLabel lblBalance;
CChartObjectLabel lblLot;
CChartObjectLabel lblTrades;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- UI setup
   CreatePanel();
   UpdatePanel();

   //--- Timer for Telegram polling
   EventSetTimer(TIMER_SECONDS);

   //--- Send Telegram start message
   SendTelegram("EA started");

   Print("ForexMoneyMachineEA initialized.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   DeletePanel();
   SendTelegram("EA stopped");
   Print("ForexMoneyMachineEA deinitialized.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!botRunning)
   {
      UpdatePanel();
      return;
   }

   //--- Loop through symbols
   for(int i = 0; i < ArraySize(Symbols); i++)
   {
      string symbol = Symbols[i];
      if(!SymbolSelect(symbol, true))
      {
         Print("Symbol not found: ", symbol);
         continue;
      }

      //--- Spread filter
      double spread = (SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(spread > 30)
      {
         Print("Spread too high for ", symbol, " | Spread: ", spread);
         continue;
      }

      //--- Prevent over-trading
      if(CountOpenTrades(symbol) >= MaxTradesPerPair)
      {
         continue;
      }

      //--- Get indicators
      double fastMA = iMA(symbol, STRATEGY_TF, FAST_MA, 0, MODE_SMA, PRICE_CLOSE, 0);
      double slowMA = iMA(symbol, STRATEGY_TF, SLOW_MA, 0, MODE_SMA, PRICE_CLOSE, 0);

      if(fastMA > slowMA)
      {
         //--- Prevent duplicate trades (same direction)
         if(!HasOpenPosition(symbol, POSITION_TYPE_BUY))
            OpenBuy(symbol);
      }
      else if(fastMA < slowMA)
      {
         if(!HasOpenPosition(symbol, POSITION_TYPE_SELL))
            OpenSell(symbol);
      }
   }

   UpdatePanel();
}

//+------------------------------------------------------------------+
//| Timer event                                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckTelegramUpdates();
}

//+------------------------------------------------------------------+
//| Chart event                                                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == "btnStart")
      {
         botRunning = true;
         UpdatePanel();
         SendTelegram("EA started");
         Print("START pressed. Bot running.");
      }
      else if(sparam == "btnStop")
      {
         botRunning = false;
         UpdatePanel();
         SendTelegram("EA stopped");
         Print("STOP pressed. Bot stopped.");
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
//+------------------------------------------------------------------+
double CalculateLotSize()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double lot = (balance * RiskPercent / 100.0) / 1000.0;
   if(lot < 0.01)
      lot = 0.01;

   // Normalize to broker min/step
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   lot = MathFloor(lot / lotStep) * lotStep;
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Count open trades for symbol                                     |
//+------------------------------------------------------------------+
int CountOpenTrades(string symbol)
{
   int total = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == symbol)
            total++;
      }
   }
   return total;
}

//+------------------------------------------------------------------+
//| Check if position exists for symbol and type                     |
//+------------------------------------------------------------------+
bool HasOpenPosition(string symbol, ENUM_POSITION_TYPE type)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == symbol &&
            PositionGetInteger(POSITION_TYPE) == type)
         {
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Open buy trade                                                   |
//+------------------------------------------------------------------+
void OpenBuy(string symbol)
{
   double lot = CalculateLotSize();
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double sl = ask - (ask * SL_PCT);
   double tp = ask + (ask * TP_PCT);

   trade.SetDeviationInPoints(10);
   if(trade.Buy(lot, symbol, ask, sl, tp, "ATM Robot"))
   {
      string msg = "ATM Robot: BUY opened on " + symbol + " at " + DoubleToString(ask, _Digits);
      Print(msg);
      SendTelegram(msg);
      SendNotification(msg);
   }
   else
   {
      Print("BUY failed on ", symbol, " | ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Open sell trade                                                  |
//+------------------------------------------------------------------+
void OpenSell(string symbol)
{
   double lot = CalculateLotSize();
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double sl = bid + (bid * SL_PCT);
   double tp = bid - (bid * TP_PCT);

   trade.SetDeviationInPoints(10);
   if(trade.Sell(lot, symbol, bid, sl, tp, "ATM Robot"))
   {
      string msg = "ATM Robot: SELL opened on " + symbol + " at " + DoubleToString(bid, _Digits);
      Print(msg);
      SendTelegram(msg);
      SendNotification(msg);
   }
   else
   {
      Print("SELL failed on ", symbol, " | ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Create control panel                                             |
//+------------------------------------------------------------------+
void CreatePanel()
{
   int x = 10;
   int y = 20;
   int w = 140;
   int h = 22;

   btnStart.Create(0, "btnStart", 0, x, y);
   btnStart.SetString(OBJPROP_TEXT, "START");
   btnStart.SetInteger(OBJPROP_XSIZE, w);
   btnStart.SetInteger(OBJPROP_YSIZE, h);
   btnStart.SetInteger(OBJPROP_COLOR, clrWhite);
   btnStart.SetInteger(OBJPROP_BGCOLOR, clrGreen);

   btnStop.Create(0, "btnStop", 0, x, y + 30);
   btnStop.SetString(OBJPROP_TEXT, "STOP");
   btnStop.SetInteger(OBJPROP_XSIZE, w);
   btnStop.SetInteger(OBJPROP_YSIZE, h);
   btnStop.SetInteger(OBJPROP_COLOR, clrWhite);
   btnStop.SetInteger(OBJPROP_BGCOLOR, clrRed);

   lblStatus.Create(0, "lblStatus", 0, x, y + 60);
   lblStatus.SetInteger(OBJPROP_COLOR, clrYellow);
   lblStatus.SetString(OBJPROP_TEXT, "BOT STOPPED");

   lblBalance.Create(0, "lblBalance", 0, x, y + 80);
   lblBalance.SetInteger(OBJPROP_COLOR, clrWhite);
   lblBalance.SetString(OBJPROP_TEXT, "Balance: ");

   lblLot.Create(0, "lblLot", 0, x, y + 100);
   lblLot.SetInteger(OBJPROP_COLOR, clrWhite);
   lblLot.SetString(OBJPROP_TEXT, "Lot: ");

   lblTrades.Create(0, "lblTrades", 0, x, y + 120);
   lblTrades.SetInteger(OBJPROP_COLOR, clrWhite);
   lblTrades.SetString(OBJPROP_TEXT, "Open Trades: ");
}

//+------------------------------------------------------------------+
//| Update control panel                                             |
//+------------------------------------------------------------------+
void UpdatePanel()
{
   string status = botRunning ? "BOT RUNNING" : "BOT STOPPED";
   lblStatus.SetString(OBJPROP_TEXT, status);

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double lot = CalculateLotSize();
   int totalTrades = PositionsTotal();

   lblBalance.SetString(OBJPROP_TEXT, "Balance: " + DoubleToString(balance, 2));
   lblLot.SetString(OBJPROP_TEXT, "Lot: " + DoubleToString(lot, 2));
   lblTrades.SetString(OBJPROP_TEXT, "Open Trades: " + IntegerToString(totalTrades));
}

//+------------------------------------------------------------------+
//| Delete control panel                                             |
//+------------------------------------------------------------------+
void DeletePanel()
{
   btnStart.Delete();
   btnStop.Delete();
   lblStatus.Delete();
   lblBalance.Delete();
   lblLot.Delete();
   lblTrades.Delete();
}

//+------------------------------------------------------------------+
//| Telegram send message                                            |
//| NOTE: Enable WebRequest in MT5:                                  |
//| Tools -> Options -> Expert Advisors -> Allow WebRequest          |
//| Add URL: https://api.telegram.org                                |
//+------------------------------------------------------------------+
void SendTelegram(string message)
{
   if(BotToken == "" || ChatID == 0)
      return;

   string url = "https://api.telegram.org/bot" + BotToken + "/sendMessage";
   string data = "chat_id=" + (string)ChatID + "&text=" + UrlEncode(message);
   char post[];
   StringToCharArray(data, post);

   char result[];
   string headers;
   int timeout = 5000;
   int res = WebRequest("POST", url, "application/x-www-form-urlencoded", timeout, post, result, headers);
   if(res == -1)
      Print("Telegram send failed: ", GetLastError());
}

//+------------------------------------------------------------------+
//| Telegram updates polling                                         |
//+------------------------------------------------------------------+
void CheckTelegramUpdates()
{
   if(BotToken == "" || ChatID == 0)
      return;

   string url = "https://api.telegram.org/bot" + BotToken + "/getUpdates?offset=" + IntegerToString(lastUpdateId + 1);
   char result[];
   string headers;
   int timeout = 5000;
   int res = WebRequest("GET", url, NULL, timeout, NULL, result, headers);
   if(res == -1)
   {
      Print("Telegram getUpdates failed: ", GetLastError());
      return;
   }

   string json = CharArrayToString(result);
   // Simple parsing for "update_id" and "text"
   int pos = StringFind(json, "\"update_id\":");
   while(pos != -1)
   {
      int start = pos + 12;
      int end = StringFind(json, ",", start);
      int upd = (int)StringToInteger(StringSubstr(json, start, end - start));
      if(upd > lastUpdateId)
         lastUpdateId = upd;

      int textPos = StringFind(json, "\"text\":\"", start);
      if(textPos != -1)
      {
         int tStart = textPos + 8;
         int tEnd = StringFind(json, "\"", tStart);
         string text = StringSubstr(json, tStart, tEnd - tStart);

         if(text == "/start" || text == "Hello")
         {
            SendTelegram("Bot is running trades now 🤖");
         }
      }

      pos = StringFind(json, "\"update_id\":", end);
   }
}

//+------------------------------------------------------------------+
//| URL encoding helper                                              |
//+------------------------------------------------------------------+
string UrlEncode(string str)
{
   string out = "";
   for(int i = 0; i < StringLen(str); i++)
   {
      ushort c = StringGetCharacter(str, i);
      if((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
         c == '-' || c == '_' || c == '.' || c == '~' || c == ' ')
      {
         if(c == ' ')
            out += "%20";
         else
            out += (string)CharToString((char)c);
      }
      else
      {
         out += "%" + StringFormat("%02X", c);
      }
   }
   return out;
}

