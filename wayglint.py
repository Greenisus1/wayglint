#!/usr/bin/env python3
"""Wayglint - explicit-search, no-key terminal maps. No background location tracking."""
import sys,argparse,curses,hashlib,io,json,math,os,queue,re,threading,time,urllib.parse,urllib.request
from pathlib import Path
from PIL import Image
VERSION='1.0.1'
HOME=Path.home()/'.local/share/wayglint'
UA='Wayglint/1.0 (https://github.com/Greenisus1/wayglint)'
DEFAULTS={'search':'https://photon.komoot.io/api/','route':'https://routing.openstreetmap.de/routed-car/route/v1/driving/','tiles':'https://tile.openstreetmap.org/{z}/{x}/{y}.png','aerial':'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}'}
LOCK=threading.Lock();LAST=0
OFFLINE=False

def clean(s):return ''.join(c for c in str(s) if c.isprintable())
def safe_home():
 for path in [HOME]+list(HOME.absolute().parents):
  if path.is_symlink():raise ValueError('Linked data path refused')
 HOME.mkdir(parents=True,exist_ok=True,mode=0o700)
def read_json(path,default):
 if path.is_symlink():raise ValueError('Linked data file refused')
 try:return json.loads(path.read_text())
 except FileNotFoundError:return default

def write_json(path,data):
 safe_home()
 if path.is_symlink():raise ValueError('Linked data file refused')
 temp=path.with_suffix('.tmp');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f)
 os.replace(temp,path)

def config():
 data=read_json(HOME/'providers.json',{})
 if not isinstance(data,dict):raise ValueError('providers.json must be an object')
 return dict(DEFAULTS,**{k:v for k,v in data.items() if k in DEFAULTS})

def get(url,ttl=86400):
 global LAST
 parsed=urllib.parse.urlparse(url)
 if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('Providers must use HTTPS without embedded credentials')
 safe_home();cache=HOME/'cache';cache.mkdir(mode=0o700,exist_ok=True)
 if cache.is_symlink():raise ValueError('Linked cache refused')
 file=cache/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
 if file.is_symlink():raise ValueError('Linked cache entry refused')
 if file.exists() and (OFFLINE or time.time()-file.stat().st_mtime<ttl):return file.read_bytes()
 if OFFLINE:raise ValueError('Offline: this request is not cached. No network used.')
 with LOCK:
  wait=2-(time.monotonic()-LAST)
  if wait>0:time.sleep(wait)
  LAST=time.monotonic()
  request=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,image/png'})
  with urllib.request.urlopen(request,timeout=15) as response:
   if urllib.parse.urlparse(response.url).scheme!='https':raise ValueError('Insecure redirect refused')
   data=response.read(5_000_001)
  if len(data)>5_000_000:raise ValueError('Provider response too large')
  fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as f:f.write(data)
  return data

def search(query):
 query=query.strip()
 if not 2<=len(query)<=200:raise ValueError('Search must be 2 to 200 characters')
 data=json.loads(get(config()['search']+'?'+urllib.parse.urlencode({'q':query,'limit':5})))
 rows=[]
 for feature in data.get('features',[])[:5]:
  lon,lat=feature['geometry']['coordinates'][:2];p=feature.get('properties',{})
  if not (-90<=lat<=90 and -180<=lon<=180):continue
  label=', '.join(str(p[k]) for k in ('name','street','city','state','country') if p.get(k))
  rows.append({'name':clean(label or query),'lat':float(lat),'lon':float(lon)})
 return rows

def tile_point(lat,lon,z):
 lat=max(-85.0511,min(85.0511,lat));n=2**z
 return (lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n

def point_latlon(x,y,z):
 n=2**z;return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n)))),x/n*360-180

def map_tile(place,z,aerial=False):
 if aerial:
  if not (24<=place['lat']<=49.4 and -125<=place['lon']<=-66):raise ValueError('Aerial mode: contiguous-US area only; coverage can have gaps. Use A for street map.')
  z=min(z,16)
 # Only tiles intersecting this explicitly requested 256x160 viewport, no prefetch.
 x,y=tile_point(place['lat'],place['lon'],z);left=x*256-128;top=y*256-80
 ix=int(left//256);iy=int(top//256);im=Image.new('RGB',(512,512),(235,235,225))
 for dx in range(int((left+255)//256)-ix+1):
  for dy in range(int((top+159)//256)-iy+1):
   tx=(ix+dx)%2**z;ty=iy+dy
   if not 0<=ty<2**z:continue
   data=get(config()['aerial' if aerial else 'tiles'].format(z=z,x=tx,y=ty),ttl=7*86400)
   part=Image.open(io.BytesIO(data));part.load()
   if part.size!=(256,256):raise ValueError('Expected 256px map tile')
   im.paste(part.convert('RGB'),(dx*256,dy*256))
 crop=(round(left-ix*256),round(top-iy*256))
 return {'image':im.crop((crop[0],crop[1],crop[0]+256,crop[1]+160)),
         'left':left,'top':top,'z':z,'x':int(x),'y':int(y),'aerial':aerial}


def directions(start,end):
 coords=f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
 data=json.loads(get(config()['route']+coords+'?steps=true&overview=full&geometries=geojson',ttl=600))
 if data.get('code')!='Ok' or not data.get('routes'):raise ValueError('No driving route returned')
 r=data['routes'][0];steps=[]
 for leg in r.get('legs',[]):
  for step in leg.get('steps',[]):
   m=step.get('maneuver',{});kind=m.get('type','continue').replace('_',' ');modifier=m.get('modifier','')
   name=clean(step.get('name') or 'unnamed road')
   steps.append(clean(f"{kind} {modifier} - {name} ({step.get('distance',0)/1000:.2f} km)"))
 return {'distance':r['distance'],'duration':r['duration'],'steps':steps,'geometry':r.get('geometry',{}).get('coordinates',[])}

def favorites():
 data=read_json(HOME/'favorites.json',[])
 if not isinstance(data,list):raise ValueError('Favorites must be a list')
 return [p for p in data[:100] if isinstance(p,dict) and all(k in p for k in ('name','lat','lon'))]

def save_favorite(place):
 rows=favorites();rows=[p for p in rows if (p['lat'],p['lon'])!=(place['lat'],place['lon'])];rows.append(place);write_json(HOME/'favorites.json',rows[-100:])

def google_link(start,end):
 # A link only, not an API call, paid service or guarantee of Google route equivalence.
 return 'https://www.google.com/maps/dir/?'+urllib.parse.urlencode({'api':1,'origin':f"{start['lat']},{start['lon']}",'destination':f"{end['lat']},{end['lon']}",'travelmode':'driving'})

def demo_tile():
 im=Image.new('RGB',(256,256),(215,225,199))
 from PIL import ImageDraw
 d=ImageDraw.Draw(im);d.rectangle((135,0,168,256),fill=(95,167,205))
 for x in range(20,250,30):d.rectangle((x,0,x+4,256),fill=(230,222,202))
 for y in range(15,250,30):d.rectangle((0,y,256,y+4),fill=(250,246,235))
 return {'image':im,'x':0,'y':0,'z':0}

def terminal_rgb(index):
 if 16<=index<=231:
  c=index-16;levels=(0,95,135,175,215,255)
  return levels[c//36],levels[c//6%6],levels[c%6]
 if 232<=index<=255:return (8+(index-232)*10,)*3
 raise ValueError('Map palette index out of range')

TERMINAL_PALETTE=[terminal_rgb(i) for i in range(16,256)]
def map_pixels(image,width,height):
 # Resize original data once; upsampling first cannot create road detail.
 scaled=image.resize((width,height*2),Image.Resampling.LANCZOS)
 # Adaptive quantization reduces half-block pair count without a fixed six-color poster effect.
 scaled=scaled.quantize(colors=32,dither=Image.Dither.NONE).convert('RGB')
 colors={rgb:min(range(240),key=lambda i:sum((a-b)**2 for a,b in zip(rgb,TERMINAL_PALETTE[i])))+16 for rgb in set(scaled.getpixel((x,y)) for y in range(scaled.height) for x in range(scaled.width))}
 return [[(colors[scaled.getpixel((x,y*2))],colors[scaled.getpixel((x,y*2+1))]) for x in range(width)] for y in range(height)]

def truecolor_rows(image,width,height,marks=()):
 im=image.resize((width,height*2),Image.Resampling.LANCZOS).convert('RGB')
 cells={(x,y):char for x,y,char in marks}
 rows=[]
 for y in range(height):
  row=[]
  for x in range(width):
   fg=im.getpixel((x,y*2));bg=im.getpixel((x,y*2+1));char=cells.get((x,y),'▀')
   if char!='▀':fg=(255,20,20);bg=(15,15,15)
   row.append('\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm%s'%(*fg,*bg,char))
  rows.append(''.join(row)+'\x1b[0m')
 return rows

def run(screen,demo=False):
 curses.curs_set(0);screen.nodelay(True);screen.keypad(True)
 colors=[curses.COLOR_BLACK,curses.COLOR_BLUE,curses.COLOR_GREEN,curses.COLOR_CYAN,curses.COLOR_RED,curses.COLOR_MAGENTA,curses.COLOR_YELLOW,curses.COLOR_WHITE]
 rgb=[(0,0,0),(30,70,170),(50,150,60),(90,170,210),(190,50,50),(150,60,160),(220,205,145),(235,235,225)]
 color=curses.has_colors()
 if color:
  curses.start_color();curses.use_default_colors()
  for i,c in enumerate(colors,1):curses.init_pair(i,c,-1)
  for i,c in enumerate(colors,9):curses.init_pair(i,c,c)
  if curses.COLORS>=256 and curses.COLOR_PAIRS>=233:
   for c in range(16,232):curses.init_pair(c+1,c,c)
 def put(y,x,text,c=8):
  h,w=screen.getmaxyx()
  if y>=0 and y<h and x>=0 and x<w-1:
   try:screen.addnstr(y,x,clean(text),w-x-1,curses.color_pair(c) if color else 0)
   except curses.error:pass
 def prompt(label):
  h,w=screen.getmaxyx();screen.nodelay(False);curses.echo();curses.curs_set(1)
  screen.move(h-2,0);screen.clrtoeol();put(h-2,1,label);screen.refresh()
  try:return screen.getstr(h-2,min(len(label)+2,w-5),max(1,w-len(label)-5)).decode('utf-8','replace')
  finally:screen.nodelay(True);curses.noecho();curses.curs_set(0)
 truecolor=os.environ.get('TERM','').startswith(('xterm','screen','tmux')) or os.environ.get('COLORTERM','').lower() in ('truecolor','24bit');aerial=False;last_ansi=None;true_cache=None;ansi_rows=None;ansi_stamp=None;render_cache=None;events=queue.Queue();busy=False;current={'name':'No place selected','lat':0,'lon':0};z=17;tile=demo_tile() if demo else None;results=[];index=0;origin=None;route=None;scroll=0;view='map';message='S search, or C enter lat,lon. Press M to load the map viewport.';privacy=False
 def background(fn,kind):
  nonlocal busy,message
  if busy:message='Wait for the current request.';return
  busy=True;message='Loading '+kind+'...'
  def job():
   try:events.put((kind,fn(),None))
   except Exception as e:events.put((kind,None,clean(str(e))))
  threading.Thread(target=job,daemon=True).start()
 def allow():
  nonlocal privacy,message
  if OFFLINE:return True
  if privacy:return True
  text=prompt('Send explicit search/coordinates to free public providers? No traffic data. y/N: ')
  privacy=text.strip().lower()=='y'
  if not privacy:message='No request sent. Demo/favorites still work.'
  return privacy
 while True:
  h,w=screen.getmaxyx();key=screen.getch()
  if key in (ord('q'),ord('Q')):return
  if key in (ord('t'),ord('T')):truecolor=not truecolor;message='Truecolor ON' if truecolor else '256-color fallback ON'
  ansi_rows=None
  while not events.empty():
   kind,value,error=events.get();busy=False
   if error:message='Provider unavailable: '+error+' (no paid fallback)';continue
   if kind=='search':results=value;index=0;view='search';message=f'{len(results)} matches. Up/Down choose, Enter selects.'
   if kind=='map':tile=value;view='map';message='Viewport loaded. Arrows move center; M reloads.'
   if kind=='route':route=value;view='route';scroll=0;message='Driving estimate only. No live traffic, closures or GPS navigation.'
  if h<23 or w<80:
   screen.erase();put(0,0,'Wayglint needs at least 80 columns x 23 rows. Resize or Q to quit.');screen.refresh();time.sleep(.05);continue
  if key in (ord('s'),ord('S')) and not busy:
   q=prompt('Search place (not confidential): ')
   if q.strip() and allow():background(lambda q=q:search(q),'search')
  elif key in (ord('c'),ord('C')):
   try:
    lat,lon=map(float,prompt('Latitude,longitude: ').split(','))
    if not(-85<=lat<=85 and -180<=lon<=180):raise ValueError('coordinates out of range')
    current={'name':f'{lat:.5f}, {lon:.5f}','lat':lat,'lon':lon};view='map';message='Center set; M fetches viewport.'
   except ValueError as e:message=clean(e)
  elif key in (ord('a'),ord('A')) and not busy:
   aerial=not aerial;message=('US AERIAL selected' if aerial else 'STREET MAP selected')+'; M loads explicit viewport.'
  elif key in (ord('m'),ord('M')) and not busy:
   if allow():background(lambda p=current.copy(),zoom=z,mode=aerial:map_tile(p,zoom,mode),'map')
  elif key in (ord('f'),ord('F')):
   try:save_favorite(current);message='Favorite saved locally.'
   except (OSError,ValueError) as e:message=clean(e)
  elif key in (ord('b'),ord('B')):
   try:results=favorites();index=0;view='search';message='Local favorites. Enter selects.'
   except (OSError,ValueError) as e:message=clean(e)
  elif key in (ord('o'),ord('O')):origin=current.copy();message='Origin set to '+current['name']
  elif key in (ord('r'),ord('R')) and not busy:
   if not origin:message='Select a place then O to set route origin; select destination, then R.'
   elif allow():background(lambda a=origin.copy(),b=current.copy():directions(a,b),'route')
  elif key in (ord('g'),ord('G')) and origin:
   link=google_link(origin,current);write_json(HOME/'last-route-link.json',{'url':link});message='Link saved locally. Run wayglint.py --last-link to copy to your phone.'
  elif key in (ord('h'),ord('H')):view='help'
  elif key==27:view='map'
  elif key in (ord('+'),ord('=')):z=min(18,z+1);message='Zoom set; M loads viewport.'
  elif key==ord('-'):z=max(2,z-1);message='Zoom set; M loads viewport.'
  elif view=='search':
   if key==curses.KEY_DOWN:index=min(max(0,len(results)-1),index+1)
   if key==curses.KEY_UP:index=max(0,index-1)
   if key in (10,13) and results:current=results[index].copy();view='map';message='Selected '+current['name']+'. M loads viewport.'
  elif view=='route':
   if key==curses.KEY_DOWN:scroll+=1
   if key==curses.KEY_UP:scroll=max(0,scroll-1)
  elif view=='map' and key in (curses.KEY_UP,curses.KEY_DOWN,curses.KEY_LEFT,curses.KEY_RIGHT):
   x,y=tile_point(current['lat'],current['lon'],z)
   x+=.25 if key==curses.KEY_RIGHT else -.25 if key==curses.KEY_LEFT else 0
   y+=.25 if key==curses.KEY_DOWN else -.25 if key==curses.KEY_UP else 0
   lat,lon=point_latlon(x%2**z,max(0,min(2**z-.0001,y)),z);current.update(lat=lat,lon=lon);message='Center moved (no network). M loads viewport.'
  screen.erase();put(0,2,'WAYGLINT  |  NO API KEYS / NO BILLING  |  '+('DEMO ART - NOT A REAL MAP' if demo else ('OFFLINE CACHE ONLY' if OFFLINE else 'FREE PUBLIC SERVICES')),4)
  put(1,2,clean(current['name'])[:w-5]);put(2,2,f"Center {current['lat']:.5f}, {current['lon']:.5f}   zoom {z}",7)
  height=h-9;width=w-4
  if view=='map' and tile:
   # Map takes left 2/3; right panel keeps important names in readable text.
   mw=max(40,width-44);mh=min(height-2,max(12,round(mw*.625/2)))
   signature=(id(tile['image']),mw,mh)
   if render_cache is None or render_cache[0]!=signature:render_cache=(signature,map_pixels(tile['image'],mw,mh))
   pixels=render_cache[1]
   capable=color and curses.COLORS>=256 and curses.COLOR_PAIRS>=60
   pairs={};next_pair=20;max_pair=min(curses.COLOR_PAIRS,32767) if color else 0
   for yy,row in enumerate(pixels if not truecolor else []):
    for xx,(topc,bottomc) in enumerate(row):
     pair=(topc,bottomc)
     if capable and pair not in pairs and next_pair<max_pair:
      curses.init_pair(next_pair,*pair);pairs[pair]=next_pair;next_pair+=1
     if capable and pair not in pairs:
      closest=min(pairs,key=lambda p:sum((a-b)**2 for a,b in zip(terminal_rgb(topc)+terminal_rgb(bottomc),terminal_rgb(p[0])+terminal_rgb(p[1]))))
      pairs[pair]=pairs[closest]
     attr=curses.color_pair(pairs[pair]) if capable else 0
     try:screen.addstr(yy+5,xx+2,'▀' if capable else ' .:-=+*#%@'[int(sum(terminal_rgb(topc))/765*9)],attr)
     except curses.error:pass
   marks=[]
   if route and 'left' in tile:
    for lon,lat in route.get('geometry',[]):
     rx,ry=tile_point(lat,lon,tile['z']);mx=(rx*256-tile['left'])/256;my=(ry*256-tile['top'])/160
     if 0<=mx<1 and 0<=my<1:
      marks.append((int(mx*mw),int(my*mh),'*'));put(5+int(my*mh),2+int(mx*mw),'*',5)
   if 'left' in tile:
    px,py=tile_point(current['lat'],current['lon'],tile['z'])
    mx=(px*256-tile['left'])/256;my=(py*256-tile['top'])/160
    if 0<=mx<1 and 0<=my<1:
     marks.append((int(mx*mw),int(my*mh),'X'));put(5+int(my*mh),2+int(mx*mw),'X',5)
   else:
    marks.append((mw//2,mh//2,'X'));put(5+mh//2,2+mw//2,'X',5)
   if truecolor:
    sig=(signature,tuple(marks))
    if true_cache is None or true_cache[0]!=sig:true_cache=(sig,truecolor_rows(tile['image'],mw,mh,marks))
    ansi_rows=true_cache[1];ansi_stamp=sig
   panel=mw+5
   put(5,panel,'SELECTED PLACE',8)
   for i,line in enumerate(__import__('textwrap').wrap(current['name'],max(20,width-mw-6))[:6]):put(7+i,panel,line,8)
   put(15,panel,'X = selected center',8)
   put(16,panel,'Zoom '+str(z)+' / loaded '+str(tile['z']),8)
   if h>=30:
    put(19,panel,'S search  F save  B saved',8)
    put(21,panel,'O origin  R directions',8)
   if route and h>=35:
    put(24,panel,f"Route: {route['distance']/1000:.1f} km",8)
    put(25,panel,f"Estimate: {route['duration']/60:.0f} min",8)
    put(27,panel,'Esc map / R route steps',8)
   put(3,2,('US AERIAL | ' if tile.get('aerial') else 'STREET MAP | ')+('RGB TRUECOLOR' if truecolor else '256-COLOR')+' | A street/aerial | T color mode',8)
   put(6+mh,2,'Road shapes are visual context, not readable street-label guarantees.',8)
  elif view=='map':put(5,3,'No map fetched yet. Search or enter coordinates, then M.',4)
  elif view=='search':
   for i,p in enumerate(results):put(5+i*2,3,('> ' if i==index else '  ')+p['name'],7 if i==index else 8)
  elif view=='route' and route:
   put(4,3,f"OSRM driving estimate: {route['distance']/1000:.1f} km, {route['duration']/60:.0f} min. NO LIVE TRAFFIC",7)
   scroll=min(scroll,max(0,len(route['steps'])-1))
   for i,text in enumerate(route['steps'][scroll:scroll+height-2]):put(6+i,3,f'{scroll+i+1}. '+text)
  elif view=='help':
   for i,text in enumerate(['S explicit Photon search; no autocomplete','C enter coordinates | M load viewport | arrows pan center | +/- zoom','O set origin | select destination | R driving route | G save Google Maps link','F save favorite locally | B show favorites | Esc map | Q quit','No live traffic/closures/GPS. Do not use while driving. Verify real road conditions.','Public searches/coordinates leave this computer. No confidential data.','Services can throttle/stop. Never a paid fallback. Endpoints in providers.json.','Data: OpenStreetMap contributors (ODbL) | tiles CC-BY-SA | routing OSRM/FOSSGIS','https://www.openstreetmap.org/copyright','https://www.openstreetmap.org/fixthemap']):put(5+i,3,text)
  put(h-4,2,message[:w-4],7);put(h-3,2,'S search | M map | +/- zoom | arrows pan | O origin | R route | F favorite | B saved | H help | Q quit',4)
  if tile and tile.get('aerial') and view=='map':
   put(h-2,2,'Aerial: USDA, USGS The National Map (historical imagery, not live)',8)
  else:put(h-2,2,'OpenStreetMap contributors (ODbL), tiles CC-BY-SA | OSRM/FOSSGIS | NO LIVE TRAFFIC',8)
  put(h-1,2,'usgs.gov | National Geospatial Program | OSM search/routes: openstreetmap.org/copyright' if tile and tile.get('aerial') and view=='map' else 'openstreetmap.org/copyright | openstreetmap.org/fixthemap',8)
  if last_ansi is not None and ansi_rows is None:screen.touchwin()
  screen.refresh()
  if ansi_rows and last_ansi!=ansi_stamp:
   # Raw RGB is drawn after curses; curses never sees untrusted escape sequences.
   sys.stdout.write('\x1b7'+''.join('\x1b[%d;3H%s'%(i+6,row) for i,row in enumerate(ansi_rows))+'\x1b[0m\x1b8');sys.stdout.flush()
  last_ansi=ansi_stamp if ansi_rows else None
  time.sleep(.1)

def main():
 global OFFLINE
 p=argparse.ArgumentParser(description='Wayglint fullscreen terminal maps; no keys or billing');p.add_argument('--offline',action='store_true',help='use only requests/tiles already cached, never connect');p.add_argument('--demo',action='store_true');p.add_argument('--last-link',action='store_true');args=p.parse_args()
 OFFLINE=args.offline
 if args.last_link:print(read_json(HOME/'last-route-link.json',{}).get('url','No route link saved.'));return 0
 try:curses.wrapper(lambda screen:run(screen,args.demo))
 except KeyboardInterrupt:pass
 except (OSError,ValueError,curses.error) as exc:print('Wayglint stopped:',clean(exc));return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
