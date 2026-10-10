import unittest,tempfile,json,io
from pathlib import Path
from unittest.mock import patch
import wayglint as a
class Maps(unittest.TestCase):
 def test_projection_roundtrip(self):
  for lat,lon in [(0,0),(51.5,-.1),(-33,150),(80,179)]:
   x,y=a.tile_point(lat,lon,12);la,lo=a.point_latlon(x,y,12);self.assertAlmostEqual(lat,la);self.assertAlmostEqual(lon,lo)
 def test_search(self):
  data={'features':[{'geometry':{'coordinates':[-.1,51.5]},'properties':{'name':'Park','city':'London'}}]}
  with patch.object(a,'get',return_value=json.dumps(data).encode()):self.assertEqual(a.search('Park')[0]['name'],'Park, London')
 def test_search_length(self):
  with self.assertRaises(ValueError):a.search('x')
 def test_route(self):
  route={'code':'Ok','routes':[{'distance':1000,'duration':100,'legs':[{'steps':[{'distance':200,'name':'Street','maneuver':{'type':'turn','modifier':'right'}}]}]}]}
  p={'lat':0,'lon':0}
  with patch.object(a,'get',return_value=json.dumps(route).encode()):self.assertIn('right',a.directions(p,p)['steps'][0])
 def test_route_fail(self):
  with patch.object(a,'get',return_value=b'{"code":"NoRoute"}'):
   with self.assertRaises(ValueError):a.directions({'lat':0,'lon':0},{'lat':1,'lon':1})
 def test_favorites_dedupe(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'HOME',Path(d)):
   p={'lat':0,'lon':0,'name':'Point'};a.save_favorite(p);a.save_favorite(p);self.assertEqual(len(a.favorites()),1)
 def test_no_controls(self):self.assertNotIn('\x1b',a.clean('\x1btest'))
 def test_no_credentials_in_url(self):
  with self.assertRaises(ValueError):a.get('https://user:pass@example.com')
 def test_no_http(self):
  with self.assertRaises(ValueError):a.get('http://example.com')
 def test_cached_no_network(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'HOME',Path(d)),patch.object(a.urllib.request,'urlopen') as net:
   cache=Path(d)/'cache';cache.mkdir();url='https://example.com';(cache/(a.hashlib.sha256(url.encode()).hexdigest()+'.bin')).write_bytes(b'cached');self.assertEqual(a.get(url),b'cached');net.assert_not_called()
 def test_viewport_center_size_and_request_bound(self):
  buf=io.BytesIO();a.Image.new('RGB',(256,256),'white').save(buf,format='PNG')
  with patch.object(a,'get',return_value=buf.getvalue()) as net:
   t=a.map_tile({'lat':52.5,'lon':13.4},16)
   self.assertEqual(t['image'].size,(256,160));self.assertLessEqual(net.call_count,4)
   x,y=a.tile_point(52.5,13.4,16);self.assertAlmostEqual(t['left']+128,x*256);self.assertAlmostEqual(t['top']+80,y*256)
 def test_viewport_antimeridian(self):
  buf=io.BytesIO();a.Image.new('RGB',(256,256),'white').save(buf,format='PNG')
  with patch.object(a,'get',return_value=buf.getvalue()) as net:
   self.assertEqual(a.map_tile({'lat':0,'lon':179.99999},16)['image'].size,(256,160))
   self.assertTrue(all('/65536/' not in c.args[0] and '/-1/' not in c.args[0] for c in net.call_args_list))
 def test_map_pixels_size_range(self):
  image=a.Image.new('RGB',(256,160),(140,190,210));pixels=a.map_pixels(image,80,24)
  self.assertEqual(len(pixels),24);self.assertEqual(len(pixels[0]),80)
  self.assertTrue(all(16<=v<=255 for row in pixels for pair in row for v in pair))
 def test_terminal_palette(self):
  self.assertEqual(a.terminal_rgb(16),(0,0,0));self.assertEqual(a.terminal_rgb(231),(255,255,255))
 def test_truecolor_rows(self):
  rows=a.truecolor_rows(a.Image.new('RGB',(256,160),(30,120,220)),8,4,[(3,2,'X')])
  self.assertEqual(len(rows),4);self.assertIn('38;2;30;120;220m',rows[0]);self.assertIn('X',rows[2]);self.assertTrue(rows[0].endswith('\x1b[0m'))
 def test_aerial_outside_us_no_request(self):
  with patch.object(a,'get') as net:
   with self.assertRaises(ValueError):a.map_tile({'lat':52.5,'lon':13.4},17,True)
   net.assert_not_called()
 def test_aerial_endpoint_zoom(self):
  buf=io.BytesIO();a.Image.new('RGB',(256,256),'green').save(buf,format='PNG')
  with patch.object(a,'get',return_value=buf.getvalue()) as net:
   t=a.map_tile({'lat':38.8893,'lon':-77.0502},17,True)
   self.assertTrue(t['aerial']);self.assertEqual(t['z'],16)
   self.assertTrue(all('nationalmap.gov' in c.args[0] and '/tile/16/' in c.args[0] for c in net.call_args_list))
 def test_link(self):self.assertIn('api=1',a.google_link({'lat':1,'lon':2},{'lat':3,'lon':4}))
 def test_demo(self):self.assertEqual(a.demo_tile()['image'].size,(256,256))
 def test_offline_miss_no_network(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'HOME',Path(d)),patch.object(a,'OFFLINE',True),patch.object(a.urllib.request,'urlopen') as net:
   with self.assertRaises(ValueError):a.get('https://example.com/missing')
   net.assert_not_called()
if __name__=='__main__':unittest.main()
