import unittest

import annorepo_tools.utils as u

big_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class UtilTestCase(unittest.TestCase):

    def test_trim_trailing_slash_1(self):
        self.assertEqual(u.trim_trailing_slash("http://some.url.org/"), "http://some.url.org")

    def test_trim_trailing_slash_2(self):
        self.assertEqual(u.trim_trailing_slash("http://some.url.org/with-path"), "http://some.url.org/with-path")

    def test_chunk_list_1(self):
        chunks = u.chunk_list(big_list, 5)
        self.assertListEqual(chunks, [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])

    def test_chunk_list_2(self):
        chunks = u.chunk_list(big_list, 4)
        self.assertListEqual(chunks, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]])

    def test_percentage_1(self):
        self.assertEqual(u.percentage(100, 100), 100)

    def test_percentage_2(self):
        self.assertEqual(u.percentage(100, 0), 0)

    def test_percentage_3(self):
        self.assertEqual(u.percentage(50, 13), 6)

    def test_calculate_xywh_1(self):
        xywh = u.calculate_xywh(ullr=[0, 0, 100, 100], width=2000, height=1000)
        self.assertEqual(xywh, "0,0,2000,1000")

    def test_calculate_xywh_2(self):
        xywh = u.calculate_xywh(ullr=[50, 50, 100, 100], width=2000, height=1000)
        self.assertEqual(xywh, "1000,500,1000,500")

    def test_calculate_xywh_without_ullr(self):
        xywh = u.calculate_xywh(ullr=None, width=2000, height=1000)
        self.assertEqual(xywh, None)

    def test_image_api_selector_with_region(self):
        expectation = {
            '@context': 'http://iiif.io/api/annex/openannotation/context.json',
            'type': 'iiif:ImageApiSelector',
            'region': "0,50,100,200"
        }
        selector = u.image_api_selector(region="0,50,100,200")
        self.assertEqual(selector, expectation)

    def test_image_api_selector_with_rotation(self):
        expectation = {
            '@context': 'http://iiif.io/api/annex/openannotation/context.json',
            'type': 'iiif:ImageApiSelector',
            'rotation': 45
        }
        selector = u.image_api_selector(rotation=45)
        self.assertEqual(selector, expectation)

    def test_image_api_selector_with_both(self):
        expectation = {
            '@context': 'http://iiif.io/api/annex/openannotation/context.json',
            'type': 'iiif:ImageApiSelector',
            'region': "x,y,w,h",
            'rotation': 90
        }
        selector = u.image_api_selector(region="x,y,w,h", rotation=90)
        self.assertEqual(selector, expectation)

    def test_image_api_selector_with_neither(self):
        expectation = {
            '@context': 'http://iiif.io/api/annex/openannotation/context.json',
            'type': 'iiif:ImageApiSelector'
        }
        selector = u.image_api_selector()
        self.assertEqual(selector, expectation)

    def test_customize_iiif_image_url_with_region(self):
        url = "https://example.org/image-service/abcd1234/full/max/0/default.jpg"
        expectation = "https://example.org/image-service/abcd1234/1,2,3,4/max/0/default.jpg"
        self.assertEqual(u.customize_iiif_image_url(url, region="1,2,3,4"), expectation)

    def test_customize_iiif_image_url_with_rotation(self):
        url = "https://example.org/image-service/abcd1234/full/max/0/default.jpg"
        expectation = "https://example.org/image-service/abcd1234/full/max/45/default.jpg"
        self.assertEqual(u.customize_iiif_image_url(url, rotation=45), expectation)

    def test_customize_iiif_image_url_with_both(self):
        url = "https://example.org/image-service/abcd1234/full/max/0/default.jpg"
        expectation = "https://example.org/image-service/abcd1234/10,20,100,200/max/33/default.jpg"
        self.assertEqual(u.customize_iiif_image_url(url, region="10,20,100,200", rotation=33), expectation)

    def test_customize_iiif_image_url_with_none(self):
        url = "https://example.org/image-service/abcd1234/full/max/0/default.jpg"
        self.assertEqual(u.customize_iiif_image_url(url), url)


if __name__ == '__main__':
    unittest.main()
