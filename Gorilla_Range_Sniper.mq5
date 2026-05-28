//+------------------------------------------------------------------+
//|                                         Gorilla_Range_Sniper.mq5 |
//|                                  Copyright 2026, Gorilla Sniper |
//|                                  High-Frequency Mean Reversion  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Gorilla Sniper"
#property version   "2.00"
#property strict
#property description "Gorilla Sniper FORTRESS MODE - Safe High-Frequency Scalper"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Input Parameters (Fortress Mode - Safe & Robust)
input int      ADX_Threshold    = 22;    // Trend Filter (M5 and M15)
input int      RSI_Oversold     = 30;    
input int      RSI_Overbought   = 70;    
input int      BB_Period        = 20;    
input double   BB_StdDev        = 2.5;   // Extreme quality entries only
input double   SL_Multiplier    = 2.5;   // MAXIMUM Breathing Room
input int      Loss_Cooldown_Mins = 10;  // Stop trading for X mins after a loss
input double   LotSize          = 0.1;   
input int      MagicNumber      = 20260527;

//--- Global Handles
int adx_h_m5, adx_h_m15, rsi_h, bb_h;
datetime last_loss_time = 0;
CTrade trade;
CPositionInfo pos_info;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   
   adx_h_m5 = iADX(_Symbol, PERIOD_M5, 14);
   adx_h_m15 = iADX(_Symbol, PERIOD_M15, 14);
   rsi_h = iRSI(_Symbol, PERIOD_M1, 14, PRICE_CLOSE);
   bb_h  = iBands(_Symbol, PERIOD_M1, BB_Period, 0, BB_StdDev, PRICE_CLOSE);
   
   if(adx_h_m5 == INVALID_HANDLE || adx_h_m15 == INVALID_HANDLE || rsi_h == INVALID_HANDLE || bb_h == INVALID_HANDLE) return(INIT_FAILED);
   
   EventSetTimer(1);
   Print("Gorilla Fortress Mode Active. Multi-TF Filtering & Cool-off enabled.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(adx_h_m5);
   IndicatorRelease(adx_h_m15);
   IndicatorRelease(rsi_h);
   IndicatorRelease(bb_h);
   Comment("");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   // --- Layer 1: Loss Cool-off Guard ---
   if(TimeCurrent() < last_loss_time + (Loss_Cooldown_Mins * 60))
   {
      long wait_secs = (last_loss_time + (Loss_Cooldown_Mins * 60)) - TimeCurrent();
      Comment("Gorilla Fortress: COOLING OFF\n",
              "Status: Protecting capital after loss.\n",
              "Resume in: ", wait_secs / 60, "m ", wait_secs % 60, "s");
      return;
   }

   // --- Layer 2: Multi-Timeframe Volatility Gate ---
   double adx_m5[1], adx_m15[1];
   if(CopyBuffer(adx_h_m5, 0, 0, 1, adx_m5) < 1 || CopyBuffer(adx_h_m15, 0, 0, 1, adx_m15) < 1) return;
   
   if(adx_m5[0] >= ADX_Threshold || adx_m15[0] >= ADX_Threshold) 
   {
      Comment("Gorilla Fortress: SHIELD ACTIVE\n",
              "M5 ADX: ", DoubleToString(adx_m5[0], 1), "\n",
              "M15 ADX: ", DoubleToString(adx_m15[0], 1), "\n",
              "Status: Trend detected. Bypassing traps.");
      return; 
   }

   // --- Layer 3: Indicator Data ---
   double rsi_buf[2], bb_up[2], bb_mid[2], bb_low[2], close_buf[2];
   if(CopyBuffer(rsi_h, 0, 0, 2, rsi_buf) < 2) return;
   if(CopyBuffer(bb_h, 0, 0, 2, bb_mid) < 2) return;
   if(CopyBuffer(bb_h, 1, 0, 2, bb_up) < 2) return;
   if(CopyBuffer(bb_h, 2, 0, 2, bb_low) < 2) return;
   if(CopyClose(_Symbol, PERIOD_M1, 0, 2, close_buf) < 2) return;

   // Check Active Positions
   bool in_trade = false;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(pos_info.SelectByIndex(i) && pos_info.Symbol() == _Symbol && pos_info.Magic() == MagicNumber)
      {
         in_trade = true;
         Comment("Gorilla Fortress: TRADE ACTIVE\nProfit: ", pos_info.Profit());
         break;
      }
   }

   // Check for recent loss to set cooldown
   HistorySelect(TimeCurrent()-3600, TimeCurrent());
   for(int i=HistoryDealsTotal()-1; i>=0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == MagicNumber && 
         HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
      {
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         if(profit < 0)
         {
            datetime deal_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
            if(deal_time > last_loss_time) 
            {
               last_loss_time = deal_time;
               Print("Loss detected. Activating 10-minute cool-off.");
            }
         }
         break;
      }
   }

   if(!in_trade)
   {
      Comment("Gorilla Fortress: SCANNING\n",
              "M5/M15 ADX: Safe\n",
              "RSI: ", DoubleToString(rsi_buf[1], 1), "\n",
              "Price: ", DoubleToString(close_buf[1], _Digits));

      // Calculate Symbol-Aware Safety SL
      double min_sl_points = 200;
      if(_Symbol == "XAUUSD" || _Symbol == "GOLD") min_sl_points = 2000; // $2.00 for Gold
      if(StringFind(_Symbol, "BTC") >= 0) min_sl_points = 5000;         // $50.00 for BTC
      
      double sl_dist = (bb_up[1] - bb_low[1]) * SL_Multiplier;
      double min_sl_val = min_sl_points * _Point;
      if(sl_dist < min_sl_val) sl_dist = min_sl_val;

      // BUY Trigger (Snap back)
      if((close_buf[0] <= bb_low[0] || rsi_buf[0] <= RSI_Oversold) && (close_buf[1] > bb_low[1] && rsi_buf[1] > RSI_Oversold))
      {
         double sl = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - sl_dist;
         Print("Gorilla Fortress: BUY. SL Distance: ", DoubleToString(sl_dist/_Point, 0), " points.");
         trade.Buy(LotSize, _Symbol, 0, sl, bb_mid[1], "Fortress BUY");
      }

      // SELL Trigger (Snap back)
      if((close_buf[0] >= bb_up[0] || rsi_buf[0] >= RSI_Overbought) && (close_buf[1] < bb_up[1] && rsi_buf[1] < RSI_Overbought))
      {
         double sl = SymbolInfoDouble(_Symbol, SYMBOL_BID) + sl_dist;
         Print("Gorilla Fortress: SELL. SL Distance: ", DoubleToString(sl_dist/_Point, 0), " points.");
         trade.Sell(LotSize, _Symbol, 0, sl, bb_mid[1], "Fortress SELL");
      }
   }
}
