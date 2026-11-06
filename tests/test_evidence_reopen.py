import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from agent import Agent


def photo_bytes(colour='red'):
    stream=io.BytesIO();Image.new('RGB',(8,8),colour).save(stream,format='PNG');return stream.getvalue()


class EvidenceReopenTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite'
        self.agent=Agent(self.path,mode='Demo')
        self.order=next(o for o in self.agent.orders.values() if o['Order_Status']=='Delivered')
        self.cid=self.order['Customer_ID'];self.oid=self.order['Order_ID'];self.session='evidence'
        self.agent.ensure_conversation(self.session,self.cid);self.agent.db.commit()
    def tearDown(self):self.agent.db.close();self.temp.cleanup()
    def test_photo_persists_and_duplicates_do_not_create_more_evidence(self):
        data=photo_bytes()
        eid=self.agent.add_photo(self.session,self.cid,self.oid,'../../damage.png',data)
        self.assertEqual(self.agent.add_photo(self.session,self.cid,self.oid,'same.png',data),eid)
        self.agent.db.close();self.agent=Agent(self.path,mode='Demo')
        photos=self.agent.photos(self.session,self.cid)
        self.assertEqual(len(photos),1);self.assertEqual(photos[0]['name'],'damage.png');self.assertEqual(photos[0]['data'],data)
    def test_invalid_photos_ownership_and_limits(self):
        with self.assertRaises(ValueError):self.agent.add_photo(self.session,self.cid,self.oid,'fake.png',b'not an image')
        with self.assertRaises(ValueError):self.agent.add_photo(self.session,self.cid,self.oid,'big.png',b'x'*(5*1024*1024+1))
        with self.assertRaises(ValueError):self.agent.add_photo(self.session,'someone-else',self.oid,'damage.png',photo_bytes())
        foreign=next(o for o in self.agent.orders.values() if o['Customer_ID']!=self.cid)
        with self.assertRaises(ValueError):self.agent.add_photo(self.session,self.cid,foreign['Order_ID'],'damage.png',photo_bytes())
        for colour in ('red','blue','green'):self.agent.add_photo(self.session,self.cid,self.oid,colour+'.png',photo_bytes(colour))
        with self.assertRaises(ValueError):self.agent.add_photo(self.session,self.cid,self.oid,'fourth.png',photo_bytes('white'))
        with self.assertRaises(ValueError):self.agent.photos(self.session,'someone-else')
    def test_reopening_records_reason_without_erasing_messages_or_requests(self):
        self.agent.log_message(self.session,self.cid,'assistant','Earlier reply');self.agent.db.commit()
        self.agent.reopen_conversation(self.session,self.cid,'Something is still pending','Still waiting for an update on the case.')
        self.assertEqual(self.agent.messages(self.session,self.cid)[0]['content'],'Earlier reply')
        self.assertIn('Still waiting',self.agent.messages(self.session,self.cid)[1]['content'])
        self.assertEqual(self.agent.db.execute('SELECT COUNT(*) FROM reopenings').fetchone()[0],1)
        self.assertEqual(self.agent.actions(self.session),[])
        with self.assertRaises(ValueError):self.agent.reopen_conversation(self.session,'other','Something is still pending','Waiting')
        with self.assertRaises(ValueError):self.agent.reopen_conversation(self.session,self.cid,'Something is still pending',' ')
        with self.assertRaises(ValueError):self.agent.reopen_conversation(self.session,self.cid,None,'Waiting')
