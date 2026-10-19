"""ETH-GBP paper trading runner. No exchange orders or credentials."""
import datetime
import json
import pathlib
import urllib.request
from urllib.parse import urlencode

ROOT = pathlib.Path(__file__).parent
PATH = ROOT / 'docs' / 'state.json'
FEE = 0.006
POSITION_FRACTION = 0.50
STOP_LOSS = 0.02
TAKE_PROFIT = 0.04
TRAIL_START = 0.025
TRAIL_DISTANCE = 0.015


def fresh():
    return {'cash': 1000.0, 'eth': 0.0, 'entry': None, 'peak': None,
            'lastCandle': 0, 'trades': [], 'lastPrice': None,
            'lastUpdate': None, 'error': None}


def candles(seconds):
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    end = (now // seconds) * seconds
    start = end - seconds * 180
    query = urlencode({
        'granularity': seconds,
        'start': datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat(),
        'end': datetime.datetime.fromtimestamp(end, datetime.timezone.utc).isoformat(),
    })
    request = urllib.request.Request(
        'https://api.exchange.coinbase.com/products/ETH-GBP/candles?' + query,
        headers={'User-Agent': 'ETH-Paper-Lab/2.0', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    if not isinstance(data, list):
        raise ValueError('Invalid market response')
    result = {}
    for row in data:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            timestamp, low, high, price = int(row[0]), float(row[1]), float(row[2]), float(row[4])
        except (TypeError, ValueError):
            continue
        if timestamp + seconds <= now and price > 0 and low <= price <= high:
            result[timestamp] = {'time': timestamp, 'price': price}
    return [result[t] for t in sorted(result)]


def ema(prices, period):
    if len(prices) < period:
        return None
    value = sum(prices[:period]) / period
    alpha = 2 / (period + 1)
    for price in prices[period:]:
        value += alpha * (price - value)
    return value


def execute(a, c, context, seconds):
    price = c['price']
    timestamp = c['time']
    if a['eth'] > 0:
        entry = a.get('entry')
        if not entry or entry <= 0:
            a['warning'] = 'Open position has no valid entry price; manual review required'
            return
        a['positionHigh'] = max(float(a.get('positionHigh') or entry), price)
        high = a['positionHigh']
        trailing = high >= entry * (1 + TRAIL_START) and price <= high * (1 - TRAIL_DISTANCE)
        if price <= entry * (1 - STOP_LOSS) or price >= entry * (1 + TAKE_PROFIT) or trailing:
            quantity = a['eth']
            proceeds = quantity * price
            fee = proceeds * FEE
            a['cash'] += proceeds - fee
            a['eth'] = 0.0
            a['entry'] = None
            a['peak'] = price
            a['positionHigh'] = None
            a['lastSellCandle'] = timestamp
            a['trades'].append({'time': timestamp * 1000, 'side': 'SELL',
                                'price': price, 'eth': quantity, 'fee': fee})
        return

    cooldown_bars = 6 if seconds == 300 else 2
    if timestamp - int(a.get('lastSellCandle') or 0) < cooldown_bars * seconds:
        return
    if len(context) < 40:
        return
    prices = [c['price'] for c in context]
    fast = ema(prices, 12)
    slow = ema(prices, 26)
    previous_fast = ema(prices[:-1], 12)
    if fast is None or slow is None or previous_fast is None:
        return
    # Buy only after a recent dip and a recovering price in a positive trend.
    recent_high = max(prices[-20:-1])
    recent_low = min(prices[-12:-1])
    dip_seen = recent_low <= recent_high * 0.992
    recovering = price > prices[-2] and fast > previous_fast
    trend_up = price > slow and fast > slow
    if not (dip_seen and recovering and trend_up):
        return
    budget = a['cash'] * POSITION_FRACTION
    if budget < 1:
        return
    fee = budget * FEE
    quantity = (budget - fee) / price
    a['cash'] -= budget
    a['eth'] = quantity
    a['entry'] = price
    a['positionHigh'] = price
    a['peak'] = None
    a['trades'].append({'time': timestamp * 1000, 'side': 'BUY',
                        'price': price, 'eth': quantity, 'fee': fee})


def main():
    try:
        state = json.loads(PATH.read_text())
        if not isinstance(state, dict):
            raise ValueError('Invalid saved state')
    except FileNotFoundError:
        state = {}
    # Do not reset balances or history on corrupt state: stop instead.
    for name, seconds in [('five', 300), ('hourly', 3600)]:
        a = state.setdefault(name, fresh())
        for key, value in fresh().items():
            a.setdefault(key, value)
        try:
            series = candles(seconds)
            if not series:
                raise ValueError('No completed candles')
            last = series[-1]
            now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            if now - last['time'] - seconds > seconds * 2 + 90:
                raise ValueError('Stale market data')
            previous = int(a.get('lastCandle') or 0)
            a['lastPrice'] = last['price']
            a['lastUpdate'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            a['error'] = None
            if not previous:
                a['lastCandle'] = last['time']
                if a['eth'] == 0:
                    a['peak'] = last['price']
            elif last['time'] > previous:
                recent = [c for c in series if c['time'] > previous]
                continuous = (bool(recent) and recent[0]['time'] - previous <= seconds * 2
                              and all(recent[i]['time'] - recent[i - 1]['time'] <= seconds * 2
                                      for i in range(1, len(recent))))
                if continuous:
                    a.pop('warning', None)
                    for c in recent:
                        context = [x for x in series if x['time'] <= c['time']]
                        execute(a, c, context, seconds)
                else:
                    a['warning'] = 'Gap in market observations; skipped uncertain fills'
                a['lastCandle'] = last['time']
            a.setdefault('history', [])
            equity = round(a['cash'] + a['eth'] * (a['lastPrice'] or a.get('entry') or 0), 4)
            stamp = a['lastUpdate']
            if not a['history'] or a['history'][-1]['time'] != stamp:
                a['history'].append({'time': stamp, 'equity': equity})
                a['history'] = a['history'][-3000:]
        except Exception as exc:
            a['error'] = str(exc)[:200]
            print(name, exc)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
