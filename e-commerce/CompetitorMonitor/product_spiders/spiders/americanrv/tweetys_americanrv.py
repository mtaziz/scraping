import re
import os

from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request, HtmlResponse
from scrapy.utils.response import get_base_url
from scrapy.utils.url import urljoin_rfc
from scrapy import log

import csv, codecs, cStringIO

from productloader import load_product
from scrapy.http import FormRequest

from product_spiders.items import Product, ProductLoader

HERE = os.path.abspath(os.path.dirname(__file__))

class TweetysSpider(BaseSpider):
    name = 'tweetys_americanrv.com'
    allowed_domains = ['www.tweetys.com', 'tweetys.com']
    start_urls = ('http://tweetys.com',)

    def __init__(self, *args, **kwargs):
        super(TweetysSpider, self).__init__(*args, **kwargs)
        self.URLBASE = 'http://tweetys.com/'
        self._items = set()
        # parse the csv file to get the product ids
        csv_file = csv.reader(open(os.path.join(HERE, 'americanrv_products.csv')))
        csv_file.next()
        self.product_ids = {}
        for row in csv_file:
            ids = row[3].split(' ')
            if ids[0] == '':
                ids = set()
            else:
                ids = set(ids)
            ids.add(row[0])
            ids.add(row[2])
            self.product_ids[row[0]] = {'mfrgid' : row[2], 'name': row[1], 'ids': frozenset(ids)}

    def start_requests(self):
        for sku, data in self.product_ids.items():
            for id in data['ids']:
                url = self.URLBASE + 'search.aspx?find=' + re.sub(' ', '+', id)
                req = Request(url)
                req.meta['sku'] = sku
                req.meta['search_q'] = id
                req.meta['mfrgid'] = data['mfrgid']
                req.meta['name'] = data['name']
                yield req

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return
        base_url = get_base_url(response)
        hxs = HtmlXPathSelector(response)

        product_urls = hxs.select('//div[@class="product-list-item"]/a/@href').extract()
        if product_urls:
            request = Request(urljoin_rfc(base_url, product_urls[0] + '?search_q=' + response.meta['search_q']), callback=self.parse_product)
            request.meta['sku'] = response.meta['sku']
            request.meta['search_q'] = response.meta['search_q']
            request.meta['mfrgid'] = response.meta['mfrgid']
            request.meta['name'] = response.meta['name']
            yield request
        else:
            return



    def parse_product(self, response):
        if not isinstance(response, HtmlResponse):
            return
        base_url = get_base_url(response)
        hxs = HtmlXPathSelector(response)
        site_mfrgid = hxs.select('//span[@class="prod-detail-man-part-value"]/text()').extract()
        if site_mfrgid:
            site_mfrgid = site_mfrgid[0].strip()
        mfrgid = response.meta['mfrgid']
        product_name = response.meta['name'].split(' ')
        if not site_mfrgid or (site_mfrgid != mfrgid and site_mfrgid not in product_name):
            return
        options = hxs.select("//select[contains(@name,'ddlVariationGroup')]/option")
        res = {}
        if not options:
            # no options
            name = hxs.select("//div[@id='product-detail-div']/h1/text()")[0].extract().strip()
            url = response.url
            price = "".join(hxs.select('//span[@class="prod-detail-cost-value"]/text()').re(r'([0-9\,\. ]+)')).strip()
            res['url'] = url
            res['description'] = response.meta['sku'] + ' ' + name
            res['price'] = price
            res['sku'] = response.meta['sku']
            res['identifier'] = response.meta['search_q']
            if (name, price) not in self._items:
                self._items.add((name, price))
                yield load_product(res, response)
        else:
            event_validation = hxs.select('//*[@id="__EVENTVALIDATION"]/@value').extract()[0]
            view_state = hxs.select('//*[@id="__VIEWSTATE"]/@value').extract()[0]

            is_multioptions = hxs.select("//select[contains(@name,'ddlVariationGroup')]")
            if len(is_multioptions) < 2:
                select_name = hxs.select("//select[contains(@name,'ddlVariationGroup')]/@name").extract()[0]
                for option in options[1:]:
                    option_value = option.select('./@value')[0].extract()
                    request = FormRequest(url=response.url,
                                  formdata={u'ctl00$MainContent$ViewTypeCheckBox': u'on',
                                            u'__EVENTTARGET': select_name,
                                            u'__EVENTARGUMENT': u'',
                                            u'__EVENTVALIDATION': event_validation,
                                            u'__VIEWSTATE': view_state,
                                            select_name: option_value},
                                  meta={'option':  option.select('./text()').extract()[0].strip(),
                                        'option_id': option_value,
                                        'sku': response.meta['sku'].lower(),
                                        'search_q': response.meta['search_q']},
                                  callback=self.parse_options)
                    yield request

    def parse_options(self, response):
        if not isinstance(response, HtmlResponse):
            return
        base_url = get_base_url(response)
        hxs = HtmlXPathSelector(response)
        res = {}
        sku_ = hxs.select("//span[@class='prod-detail-part-value']/text()[contains(.,'" + response.meta['search_q'] + "')]").extract()
        # log.msg('SEARCH_Q: '+ response.meta['search_q'])
        if sku_:
            main_name = hxs.select("//div[@id='product-detail-div']/h1/text()")[0].extract().strip()
            name = '%s %s' % (main_name, response.meta['option'].strip())
            url = response.url
            price = "".join(hxs.select('//span[@class="prod-detail-cost-value"]/text()').re(r'([0-9\,\. ]+)')).strip()
            res['url'] = url
            res['description'] = name
            res['price'] = price
            res['sku'] = response.meta['sku']
            res['identifier'] = '%s-%s' % (response.meta['search_q'], response.meta['option_id'])
            if (name, price) not in self._items:
                self._items.add((name, price))
                yield load_product(res, response)
