import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import agent


class ServiceViewsTests(unittest.TestCase):
    def test_support_update_persists_and_reaches_customer_and_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=agent.Agent
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(tmp)/'views.sqlite'
                return original(*args,**kwargs)
            with patch('agent.Agent',side_effect=isolated), patch.dict('os.environ',{'APP_ENV':'local','APP_MODE':'Demo','SUPPORT_ACCESS_CODE':'','ADMIN_ACCESS_CODE':''}):
                app=AppTest.from_file(str(agent.ROOT/'app.py')).run()
                backend=app.session_state['agent']
                order=next(o for o in backend.orders.values() if o['Order_Status']=='Confirmed')
                cid=order['Customer_ID'];session='service-test'
                result=backend.chat('Cancel '+order['Order_ID'],session=session,customer_id=cid)
                request_id=backend.confirm(result,session)
                next(r for r in app.radio if r.label=='Interface').set_value('Support').run()
                self.assertEqual(len(app.exception),0)
                next(s for s in app.selectbox if s.label=='Status').set_value('completed')
                next(t for t in app.text_input if t.label=='Assigned to').set_value('Test Expert')
                next(t for t in app.text_area if t.label=='Reply visible to the customer').set_value('Your cancellation is complete.')
                next(b for b in app.button if b.label=='Save update').click().run()
                self.assertEqual(len(app.exception),0)
                request=next(r for r in backend.support_actions() if r['id']==request_id)
                self.assertEqual(request['status'],'completed')
                self.assertEqual(request['assignee'],'Test Expert')
                self.assertIn('Your cancellation is complete.',backend.messages(session,cid)[-1]['content'])
                tracking=backend.chat('Where is '+order['Order_ID']+'?',session=session,customer_id=cid)
                self.assertIn('cancelled',tracking['response'])
                next(r for r in app.radio if r.label=='Interface').set_value('Admin').run()
                self.assertEqual(len(app.exception),0)
                self.assertTrue(any('Service overview' in t.label for t in app.tabs))
                backend.db.close()
