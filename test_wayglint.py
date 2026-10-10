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
 def test_link(self):self.assertIn('api=1',a.google_link({'lat':1,'lon':2},{'lat':3,'lon':4}))
 def test_demo(self):self.assertEqual(a.demo_tile()['image'].size,(256,256))
 def test_offline_miss_no_network(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'HOME',Path(d)),patch.object(a,'OFFLINE',True),patch.object(a.urllib.request,'urlopen') as net:
   with self.assertRaises(ValueError):a.get('https://example.com/missing')
   net.assert_not_called()
if __name__=='__main__':unittest.main()
