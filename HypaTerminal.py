#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 31 14:32:56 2022

@author: Diego
"""

from yahoo_fin import options as op
import streamlit as st
import yfinance as yf
import pandas as pd
from streamlit_option_menu import option_menu
import cufflinks as cf
from datetime import datetime
import datetime as dt
import numpy as np
import matplotlib
from pycoingecko import CoinGeckoAPI
import yahoo_fin.stock_info as si
import macrodatabase as md
from fredapi import Fred
from fred_api_key import fred
import inquisitor
from itertools import chain
import matplotlib.pyplot as plt
from matplotlib import cm
import tkinter as tk


matplotlib.use('TkAgg')
qb = inquisitor.Inquisitor()
# App title
st.markdown('''
# HypaTerminal
Inspired by OpenBBTerminal, this is my first project and I hope you enjoy it!
''')

# horizontal menu
selected = option_menu(
    menu_title=None,
    options=['Stocks', 'Crypto', 'Economy', 'Forex'],
    icons=['graph-up-arrow', 'currency-bitcoin', 'globe', 'currency-exchange'],
    menu_icon='cast',
    default_index=0,
    orientation='horizontal',
)


if selected == 'Stocks':
    st.header('Stocks')
    st.sidebar.subheader('Symbol Search')
    start_date = st.sidebar.date_input("Start date", datetime(2019, 1, 1))
    end_date = st.sidebar.date_input("End date", datetime.now().date())

# Retrieving tickers data
    tickerList = pd.read_csv('https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/allsymbols.txt')
    tickerSymbol = st.sidebar.selectbox('Stock ticker', tickerList) # select ticker
    tickerData = yf.Ticker(tickerSymbol) # get ticker data
    tickerDf = tickerData.history(period='1d', start=start_date, end=end_date) # get historical prices for ticker
    stock = yf.Ticker(tickerSymbol)

# compare stocks 
    #dropdown = st.multiselect('Pick your assets',
                              #tickerList)
    compareStocks = st.sidebar.multiselect('Compare stocks', tickerList)
    
    def relativeret(df):
        rel = df.pct_change()
        cumret = (1+rel).cumprod() - 1
        cumret = cumret.fillna(0)
        return cumret
    
    if len(compareStocks) > 0:
        df = relativeret(yf.download(compareStocks,start_date,end_date)['Adj Close'])
        st.line_chart(df)  
    
    
    # get expiration dates
    expirationDates = op.get_expiration_dates(tickerSymbol)

#call and put option data
    callData = op.get_calls(tickerSymbol, date = expirationDates[0])
    putData = op.get_puts(tickerSymbol, date = expirationDates[0])

#ticker information
    string_logo = '<img src=%s>' % tickerData.info['logo_url']
    st.markdown(string_logo, unsafe_allow_html=True)

    string_name = tickerData.info['longName']
    st.header('**%s**' % string_name)

    string_summary = tickerData.info['longBusinessSummary']
    st.info(string_summary)

# ticker data
    st.header('**Ticker data**')
    st.dataframe(tickerDf)

# Candle chart of stocks
    st.header('**Candle chart**')
    qf=cf.QuantFig(tickerDf,title=tickerSymbol,legend='top')
    qf.add_volume()
    fig = qf.iplot(asFigure=True)
    st.plotly_chart(fig)

# request time series data
    ts = si.get_data(tickerSymbol, start_date, end_date)
    
    #daily log returns
    ts['logRet'] = np.log(ts['adjclose']/ts['adjclose'].shift(1))
    ts['logRet'] = ts['logRet'].fillna(0)
    
# adjustment Ratio
    ts['adjustmentRatio'] = ts['adjclose']/ts['close']

# adjusted OHL prices 
    ts['adjOpen'] = ts['open'] * ts['adjustmentRatio']
    ts['adjLow'] = ts['low'] * ts['adjustmentRatio']
    ts['adjHigh'] = ts['high'] * ts['adjustmentRatio']   

# average true range for stock
    avgTrueRangeWindow = 20
    ts['Method1'] = ts['adjHigh'] - ts['adjLow']
    ts['Method2'] = abs((ts['adjHigh'] - ts['adjclose'].shift(1)))
    ts['Method3'] = abs((ts['adjLow'] - ts['adjclose'].shift(1)))
    ts['Method1'] = ts['Method1'].fillna(0)
    ts['Method2'] = ts['Method2'].fillna(0)
    ts['Method3'] = ts['Method3'].fillna(0)
    ts['TrueRange'] = ts[['Method1','Method2','Method3']].max(axis = 1)

    ts['avgTrueRangePoints'] = ts['TrueRange'].rolling(
        window = avgTrueRangeWindow, center=False).mean()
    avgtrueRange = ts['avgTrueRangePoints']

    st.line_chart(avgtrueRange)
    
# call option data
    st.header('**Call option data**')
    exp_dates = expirationDates
    option = st.selectbox('Choose expiration date', exp_dates, 0)
    st.write('You selected:', option)
    st.dataframe(callData)


# call option bar chart
    cdata = pd.pivot_table(callData,index=['Strike'],values=['Volume','Open Interest'])
    #st.bar_chart(cdata)
    call_fig = cdata.iplot(kind='bar',
                           barmode='stack',
                           xTitle='Strike',
                           yTitle='Number of contracts',
                           title=tickerSymbol + ' Calls OI vs Volume',
                           legend='top',
                           asFigure=True,
                           opacity=1.0
                           );
    st.plotly_chart(call_fig)
    
    #plotting 3d volatility surface
    # store maturities 
    #st.header('**3d Volatility surface**')
    lMaturity = list(stock.options)

    # get current date
    today = datetime.now().date()
    # empty list for days to expiration
    lDTE = []
    # empty list to store data for calls
    lData_calls = []
    # loop over maturities
    for maturity in lMaturity:
        # maturity date
        maturity_date = datetime.strptime(maturity, '%Y-%m-%d').date()
        # DTE: difference between maturity date and today
        lDTE.append((maturity_date - today).days)
        # store call data
        lData_calls.append(stock.option_chain(maturity).calls)
        
     # create empty lists to contain unlisted data
    lStrike = []
    lDTE_extended = []
    lImpVol = []
    for i in range(0,len(lData_calls)):
        # append strikes to list
        lStrike.append(lData_calls[i]["strike"])
        # repeat DTE so the list has same length as the other lists
        lDTE_extended.append(np.repeat(lDTE[i], len(lData_calls[i])))
        # append implied volatilities to list
        lImpVol.append(lData_calls[i]["impliedVolatility"])
        
    # unlist list of lists
    lStrike = list(chain(*lStrike))
    lDTE_extended = list(chain(*lDTE_extended))
    lImpVol = list(chain(*lImpVol))   

    # initiate figure
    fig = plt.figure()
    # set projection to 3d
    axs = plt.axes(projection="3d")
    # use plot_trisurf from mplot3d to plot surface and cm for color scheme
    axs.plot_trisurf(lStrike, lDTE_extended, lImpVol, cmap=cm.jet,)
    # change angle
    axs.view_init(30, 65)
    # add labels
    plt.xlabel("Strike")
    plt.ylabel("DTE")
    plt.title("Volatility Surface for $"+tickerSymbol+": Calls IV as a Function of K and T")
    plt.show()
    st.pyplot(fig)
    
    
# put option data
    st.header('**Put option data**')
    if option:
        st.write('You selected:', option)
        st.dataframe(putData)

# put option bar chart
    pdata = pd.pivot_table(putData,index=['Strike'],values=['Volume','Open Interest'])
    #st.dataframe(pdata)
    #st.bar_chart(pdata)
    bar_fig = pdata.iplot(kind='bar',
                          barmode='stack',
                          xTitle='Strike',
                          yTitle='Number of contracts',
                          title=tickerSymbol + ' Puts OI vs Volume',
                          legend='top',
                          asFigure=True,
                          opacity=1.0
                          );
    st.plotly_chart(bar_fig)

    #plotting 3d volatility surface
    # store maturities 
    #st.header('**3d Volatility surface**')
    lMaturity = list(stock.options)

    # get current date
    today = datetime.now().date()
    # empty list for days to expiration
    lDTE = []
    # empty list to store data for puts
    lData_puts = []
    # loop over maturities
    for maturity in lMaturity:
        # maturity date
        maturity_date = datetime.strptime(maturity, '%Y-%m-%d').date()
        # DTE: difference between maturity date and today
        lDTE.append((maturity_date - today).days)
        # store put data
        lData_puts.append(stock.option_chain(maturity).puts)
        
     # create empty lists to contain unlisted data
    lStrike = []
    lDTE_extended = []
    lImpVol = []
    for i in range(0,len(lData_puts)):
        # append strikes to list
        lStrike.append(lData_puts[i]["strike"])
        # repeat DTE so the list has same length as the other lists
        lDTE_extended.append(np.repeat(lDTE[i], len(lData_puts[i])))
        # append implied volatilities to list
        lImpVol.append(lData_puts[i]["impliedVolatility"])
        
    # unlist list of lists
    lStrike = list(chain(*lStrike))
    lDTE_extended = list(chain(*lDTE_extended))
    lImpVol = list(chain(*lImpVol))   

    # initiate figure
    fig = plt.figure()
    # set projection to 3d
    axs = plt.axes(projection="3d")
    # use plot_trisurf from mplot3d to plot surface and cm for color scheme
    axs.plot_trisurf(lStrike, lDTE_extended, lImpVol, cmap=cm.jet,)
    # change angle
    axs.view_init(30, 65)
    # add labels
    plt.xlabel("Strike")
    plt.ylabel("DTE")
    plt.title("Volatility Surface for $"+tickerSymbol+": Puts IV as a Function of K and T")
    plt.show()
    st.pyplot(fig)


# crypto page
elif selected == 'Crypto':
    st.header('Crypto')
    st.sidebar.subheader('Symbol Search')
    start_date = st.sidebar.date_input("Start date", datetime(2019, 1, 1))
    end_date = st.sidebar.date_input("End date", datetime.now().date())
    
    cg = CoinGeckoAPI() #create a client
    
    cg.ping() #confirm connection
    
    # coins list
    coinList = cg.get_coins_list()
    coinDataFrame = pd.DataFrame.from_dict(coinList).sort_values('id'
                                                                 ).reset_index(drop=True)
    
    #cryptos by id
    coins = ['bitcoin', 'ethereum', 'dopex', 'solana', 'meta', 'litecoin', 'dogecoin', 'xrp', 'cardano', 'monero', 'kadena']
    
    #get list of supported VS currencies
    counterCurrencies = cg.get_supported_vs_currencies()
    vsCurrencies = ['usd', 'eur', 'link']
    cryptolist = st.sidebar.selectbox('Crypto tickers', coins)

    # price request
    st.header(cryptolist)
    complexPriceRequest = cg.get_price(ids = cryptolist,
                                       vs_currencies = vsCurrencies,
                                       include_market_cap = True,
                                       include_24hr_vol = True,
                                       include_24hr_change = True,
                                       include_last_updated_at = True)
    st.dataframe(complexPriceRequest)
    
    # get coin history by single id
    coinHistory = cg.get_coin_history_by_id(id = cryptolist,
                                            date = dt.datetime.today().strftime('%d-%m-%Y'))
    
    #get daily historical data
    dailyHistoricalData = cg.get_coin_market_chart_by_id(id = cryptolist,
                                                         vs_currency = 'usd',
                                                         days = 'max')
    #st.dataframe(dailyHistoricalData)
    #get hourly historical data
    hourlyHistoricalData = cg.get_coin_market_chart_by_id(id = cryptolist,
                                                          vs_currency = 'usd',
                                                          days = 90)
    
    #get 5 minute historical data
    fiveMinHistoricalData = cg.get_coin_market_chart_by_id(id = cryptolist,
                                                           vs_currency = 'usd',
                                                           days = 1)
    
    #list of lists to dataframe
    dailyHistoricalDataFrame = pd.DataFrame(data = dailyHistoricalData['prices'],
                                            columns = ['Date', 'Price'])
    #reformat date
    dailyHistoricalDataFrame['Date'] = dailyHistoricalDataFrame['Date'].apply(
        lambda x: dt.datetime.fromtimestamp(x/1000).strftime('%m-%d-%Y'))
    #set index
    dailyHistoricalDataFrame = dailyHistoricalDataFrame.set_index('Date')
    
    #plot                    
    st.header('**Candle Chart**')
    qf=cf.QuantFig(dailyHistoricalDataFrame['Price'],title=cryptolist,legend='top')
    fig1 = qf.iplot(asFigure=True)
    st.plotly_chart(fig1)
    
    ohlcData = cg.get_coin_ohlc_by_id(id = cryptolist,
                                      vs_currency = 'usd',
                                      days = '14')
    #list to dataframe
    ohlcDataFrame = pd.DataFrame(data = ohlcData,
                                 columns = ['Date', 'Open', 'High', 'Low', 'Close'])
    #reformat date
    ohlcDataFrame['Date'] = ohlcDataFrame['Date'].apply(
                            lambda x: dt.datetime.fromtimestamp(x/1000
                            ).strftime('%m-%d-%Y %H:%M:%S'))
    #set index
    ohlcDataFrame = ohlcDataFrame.set_index('Date')
    qf=cf.QuantFig(ohlcDataFrame,title=cryptolist,legend='top')
    fig2 = qf.iplot(asFigure=True)
    st.plotly_chart(fig2)

    #get trending search coins
    trendingCoins = cg.get_search_trending()['coins']
    
    
    
 # economy page   
elif selected == 'Economy':
   countries = ['Afghanistan',
   'Albania',
   'Algeria',
   'Angola',
   'Anguilla',
   'Argentina',
   'Armenia',
   'Aruba',
   'Azerbaijan',
   'Bahamas',
   'Bangladesh',
   'Barbados',
   'Belarus',
   'Belize',
   'Benin',
   'Bosnia and Herzegovina',
   'Botswana',
   'Brunei Darussalam',
   'Bulgaria',
   'Burkina Faso',
   'Burundi',
   'Cambodia',
   'Cameroon',
   'Central African Republic',
   'Chad',
   'Chile',
   'Colombia',
   'Comoros',
   'Costa Rica',
   'Croatia',
   'Cyprus',
   'Czech Republic',
   'Djibouti',
   'Dominica',
   'Dominican Republic',
   'Ecuador',
   'Egypt',
   'El Salvador',
   'Equatorial Guinea',
   'Estonia',
   'Ethiopia',
   'Fiji',
   'Gabon',
   'Ghana',
   'Grenada',
   'Guatemala',
   'Guinea',
   'Guinea-Bissau',
   'Guyana',
   'Honduras',
   'Hungary',
   'Iceland',
   'Iraq',
   'Israel',
   'Jamaica',
   'Jordan',
   'Kazakhstan',
   'Kenya',
   'Kiribati',
   'Kosovo',
   'Kuwait',
   'Kyrgyz Republic',
   "Lao People's Democratic Republic",
   'Latvia',
   'Lebanon',
   'Lesotho',
   'Liberia',
   'Lithuania',
   'Madagascar',
   'Malawi',
   'Maldives',
   'Mali',
   'Malta',
   'Marshall Islands',
   'Mauritania',
   'Mauritius',
   'Mongolia',
   'Montenegro',
   'Montserrat',
   'Morocco',
   'Mozambique',
   'Myanmar',
   'Namibia',
   'Nepal',
   'Nicaragua',
   'Niger',
   'Nigeria',
   'Pakistan','Palau','Panama','Papua New Guinea','Paraguay','Peru','Philippines','Qatar','Romania','Rwanda','Samoa','San Marino','Sao Tome and Principe','Saudi Arabia','Senegal','Serbia','Seychelles','Sierra Leone','Solomon Islands','South Sudan','Sudan','Suriname','Swaziland','Syrian Arab Republic','Tajikistan','Timor-Leste','Togo','Tonga','Trinidad and Tobago','Tunisia','Uganda','Ukraine','United Arab Emirates','Uruguay','Uzbekistan','Vanuatu','Zambia']
   
   choices = st.multiselect('select country(s)', countries)
   #st.write('You selected:', choices)
   md.show_database_options(search='Inflation')
   
   
   md.show_states_options()
   md.select_country_data(category='Prices', parameter='CPIEALL', country=countries, unit=None, period=None, seasonality=True)

   ql = qb.datasets(source='Country all')
   st.dataframe(ql)
