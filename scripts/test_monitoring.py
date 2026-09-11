import unittest
from datetime import date
import monitoring as m

class MonitoringTests(unittest.TestCase):
    def test_semantic_rules(self):
        from source_matching import match_items
        def retail(name):return {'name':name,'kind':'retail','points':[]}
        def upstream(id,name):return {'id':id,'name':name,'kind':'farm' if id.startswith('farm') else 'reference','market':'台南','points':[{'month':'2026-08','reference':10}]}
        rows=[retail('小黃瓜1台斤'),retail('芭樂1台斤'),retail('梅花肉1台斤'),retail('鮭魚1斤'),retail('虱目魚肚1斤'),retail('蚵1斤'),upstream('farm-a','花胡瓜'),upstream('farm-b','番石榴-珍珠芭'),upstream('livestock-c','毛豬規格豬'),upstream('fish-d','鮭魚頭/尾'),upstream('fish-e','虱目魚'),upstream('farm-f','小白菜-蚵仔白')]
        match_items(rows)
        self.assertEqual(rows[0]['default_comparison'],'farm-a')
        self.assertEqual(rows[1]['default_comparison'],'farm-b')
        self.assertEqual(rows[2]['comparison_level'],'upstream')
        self.assertFalse(rows[3]['candidates'])
        self.assertFalse(rows[4]['candidates'])
        self.assertFalse(rows[5]['candidates'])

    def points(self):
        now=date.today(); end=now.year*12+now.month-1
        return [{'month':f'{i//12:04d}-{i%12+1:02d}','retail':120.,'wholesale':100.} for i in range(end-17,end+1)]

    def test_dates_and_missing(self):
        self.assertEqual(m.parse_date('1150904'),'2026-09-04')
        self.assertEqual(m.parse_date('115.09.04'),'2026-09-04')
        self.assertIsNone(m.parse_date('2026-02-30'))
        for v in [None,'',0,-1,'NaN','Infinity']:
            self.assertIsNone(m.number(v))

    def test_current_month_excluded(self):
        p=self.points(); baseline=m.assess(p); p[-1]['retail']=200
        alert=m.assess(p)
        self.assertEqual(alert['status'],'待查證異常')
        self.assertEqual(baseline['lower'],alert['lower'])
        self.assertEqual(baseline['upper'],alert['upper'])
        self.assertEqual(alert['n'],17)

    def test_insufficient_unapproved_stale(self):
        self.assertEqual(m.assess(self.points()[-8:])['status'],'資料不足')
        self.assertEqual(m.assess(self.points(),False)['status'],'待確認配對')
        p=self.points()
        for i,x in enumerate(p): x['month']=f'2020-{i%12+1:02d}' if i<12 else f'2021-{i%12+1:02d}'
        self.assertEqual(m.assess(p)['status'],'資料逾期')

    def test_calendar_window(self):
        p=self.points()
        for x in p[:-1]: x['month']='2001'+x['month'][4:]
        self.assertEqual(m.assess(p)['status'],'資料不足')

    def test_build_integrity(self):
        p=m.build()
        self.assertEqual(len([i for i in p['items'] if i['kind']=='retail']),28)
        self.assertEqual(len(p['retail_months']),51)
        self.assertEqual(p['retail_months'][0],'2022-06')
        self.assertEqual(p['retail_months'][-1],'2026-08')
        self.assertIn('鴨母寮市場',p['markets'])
        self.assertIn('開元市場',p['markets'])
        self.assertEqual(p['retail_import_audit']['duplicate_months_removed'],31)
        self.assertEqual(len({i['id'] for i in p['items']}),len(p['items']))
        self.assertTrue(p['source_manifest'])
        for item in p['items']:
            if item['kind']=='retail': self.assertNotEqual(item['assessment']['status'],'待查證異常')
            self.assertEqual(item['unit'],'元／公斤')

if __name__=='__main__': unittest.main()
