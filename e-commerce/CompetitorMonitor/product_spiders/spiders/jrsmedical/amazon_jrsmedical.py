import csv
import os
import copy
import re

from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request, HtmlResponse, FormRequest
from scrapy.utils.response import get_base_url
from scrapy.utils.url import urljoin_rfc
from scrapy.http.cookies import CookieJar

from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader

HERE = os.path.abspath(os.path.dirname(__file__))

class AmazonJRSMedicalSpider(BaseSpider):
    name = 'amazon_jrsmedical.com'
    allowed_domains = ['amazon.com']
    user_agent = 'spd'

    def start_requests(self):
        with open(os.path.join(HERE, 'jrsmedical_products.csv')) as f:
            reader = csv.reader(f)
            reader.next()
            reader = set([row[1] for row in reader])
            for row in reader:
                sku = row
                query = sku.replace(' ', '+')
                url = 'http://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%%3Dhpc&field-keywords=%s'
                yield Request(url % query, meta={'sku': sku})

    def parse(self, response):
        hxs = HtmlXPathSelector(response)

        products = hxs.select('//div[@id="atfResults"]//div[starts-with(@id, "result_")]')
        pr = None
        for product in products:
            loader = ProductLoader(item=Product(), selector=product)
            loader.add_xpath('name', './/*[contains(@class, "Title") or contains(@class, "title")]//a/text()')

            loader.add_xpath('url', './/*[contains(@class, "Title") or contains(@class, "title")]//a/@href')
            loader.add_xpath('price', './/*[@class="subPrice"]/a[contains(text(), "new")]' +
                                      '/following-sibling::*[@class="price"]/text()')
            loader.add_xpath('price', './/*[@class="newPrice"]//span/text()')
            loader.add_value('sku', response.meta['sku'])
            loader.add_value('identifier', response.meta['sku'])
            if loader.get_output_value('price') and (pr is None or pr.get_output_value('price') >
                                                                   loader.get_output_value('price')):
                pr = loader

        if pr:
            yield pr.load_item()
