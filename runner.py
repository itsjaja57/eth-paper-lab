import json, os, urllib.request, datetime, pathlib
from urllib.parse import urlencode
ROOT=pathlib.Path(__file__).parent
PATH=ROOT/'docs'/'state.json'
FEE=.006

def fresh():
 return {'cash':1000.,'eth':0.,'entry':None,'peak':None,'lastCandle':0,'trades':[],'lastPrice':None,'lastUpdate':None,'error':None}

def candles(seconds):
 now=int(datetime.datetime.now(datetime.timezone.utc).timestamp())
 end=(now//seconds)*seconds
 start=end-seconds*100
 q=urlencode({'granularity':seconds,'start':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'end':datetime.datetime.fromtimestamp(end,datetime.timezone.utc).isoformat()})
 req=urllib.request.Request('https://api.exchange.coinbase.com/products/ETH-GBP/candles?'+q,headers={'User-Agent':'ETH-Paper-Lab/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r: data=json.load(r)
 if not isinstance(data,list):raise ValueError('Invalid market response')
 out=[]
 for c in data:
  if not isinstance(c,list) or len(c)<6:continue
  try:t=int(c[0]);p=float(c[4]);lo=float(c[1]);hi=float(c[2])
  except (ValueError,TypeError):continue
  if t+seconds<=now and p>0 and lo<=p<=hi:out.append({'time':t,'price':p})
 return sorted({x['time']:x for x in out}.values(),key=lambda x:x['time'])

def trade(a,c):
 p=c['price']
 if a['eth']==0:
  a['peak']=max(a['peak'] or p,p)
  if p<=a['peak']*.995:
   fee=a['cash']*FEE;qty=(a['cash']-fee)/p
   if qty>0:
    a.update(cash=0.,eth=qty,entry=p,peak=None)
    a['trades'].append(dict(time=c['time']*1000,side='BUY',price=p,eth=qty,fee=fee))
 elif a['entry'] and (p>=a['entry']*1.03 or p<=a['entry']*.98):
  qty=a['eth'];fee=qty*p*FEE
  a.update(cash=qty*p-fee,eth=0.,entry=None,peak=p)
  a['trades'].append(dict(time=c['time']*1000,side='SELL',price=p,eth=qty,fee=fee))

def main():
 try:state=json.loads(PATH.read_text())
 except (FileNotFoundError,ValueError):state={}
 for name,seconds in [('five',300),('hourly',3600)]:
  a=state.setdefault(name,fresh())
  for k,v in fresh().items():a.setdefault(k,v)
  try:
   series=candles(seconds)
   if not series:raise ValueError('No completed candles')
   last=series[-1];now=int(datetime.datetime.now(datetime.timezone.utc).timestamp())
   if now-last['time']-seconds>seconds*2+90:raise ValueError('Stale market data')
   a['lastPrice']=last['price'];a['lastUpdate']=datetime.datetime.now(datetime.timezone.utc).isoformat();a['error']=None
   prev=a['lastCandle']
   if not prev:
    a['lastCandle']=last['time'];a['peak']=last['price'] if a['eth']==0 else a['peak']
   elif last['time']>prev:
    recent=[c for c in series if c['time']>prev]
    continuous=bool(recent) and recent[0]['time']-prev<=seconds*2 and all(recent[i]['time']-recent[i-1]['time']<=seconds*2 for i in range(1,len(recent)))
    if continuous:
     for c in recent:trade(a,c)
    else:
     if a['eth']==0:a['peak']=last['price']
     a['warning']='Gap in market observations; skipped uncertain fills'
    a['lastCandle']=last['time']
  except Exception as exc:
   a['error']=str(exc)[:200]
   print(name,exc)
 PATH.write_text(json.dumps(state,indent=2)+'\n')
if __name__=='__main__':main()
