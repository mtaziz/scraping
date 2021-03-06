# -*- coding: utf-8 -*-

from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from scrapy.utils.response import get_base_url
from scrapy.contrib.loader.processor import Compose
from urlparse import urljoin
from product_spiders.items import Product, ProductLoader
import re

from product_spiders.spiders.lego_cz.legobase import LegoMetadataBaseSpider


class KdosihrajeSpider(LegoMetadataBaseSpider):
    name = u'kdosihraje.cz'
    allowed_domains = ['www.kdosihraje.cz']
    start_urls = [
        u'http://www.kdosihraje.cz/lego-4.html',
        u'http://www.kdosihraje.cz/duplo.html',
    ]
    errors = []
    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        base_url = get_base_url(response)

        next_page = hxs.select(u'//div[@class="pages"]/ol/li/a[@class="next i-next"]/@href').extract()
        items = hxs.select('//div[@class="category-products"]/ul/li/a/@href').extract()
        for url in items:
            yield Request(urljoin(base_url, url), callback=self.parse_product)
        if next_page:
            yield Request(urljoin(base_url, next_page.pop()), callback=self.parse)

    def parse_price(self, price):
        try:
            price, count = re.subn(r'[^0-9 .,]*([0-9 .,]+)\W*K.*', r'\1', price.strip())
        except TypeError:
            return False
        if count:
            price = price.replace(",", "").replace(" ", "")
            try:
                price = float(price)
            except ValueError:
                return False
            else:
                return price
        elif price.isdigit():
            return float(price)
        return False

    def get_sku_from_text(self, text):
        try:
            #id, count = re.subn(r'^[^0-9]*[^\.]{1}\W([0-9]{4,6}).*$', r'\1', text)
            id, count = re.subn(r'^[^0-9]*[^,\. 0-9][ ]?([0-9]{4,6}).*$', r'\1', text)
        except TypeError:
            return ""
        if count:
            id = id.strip()
            try:
                int(id)
            except ValueError:
                return ""
            else:
                return id
        return False

    def parse_product(self, response):

        hxs = HtmlXPathSelector(response)
        base_url = get_base_url(response)

        name = hxs.select('//div[@class="product-name"]/h1/text()').extract().pop().strip()

        category = hxs.select('//div[@class="breadcrumbs"]/ul/li/a/text()').pop().extract().strip()
        if category.startswith(u'Dom\u016f'):
            category = ""

        sku = self.get_sku_from_text(name)

        pid = hxs.select('//input[@name="product"]/@value').pop().extract()

        if not sku:
            sku = ""

        price = self.parse_price("".join(hxs.select('//span[contains(@id, "product-price")]/descendant-or-self::text()').extract()))

        #stock = hxs.select('//p[@class="availability in-stock"]')

        if price:
            loader = ProductLoader(response=response, item=Product())
            loader.add_value('url', urljoin(base_url, response.url))
            loader.add_value('name', name)
            loader.add_xpath('image_url', '//div[@class="product-img-box"]/p/img/@src', Compose(lambda v: urljoin(base_url, v[0])))
            loader.add_value('price', price)
            loader.add_value('category', category)
            loader.add_value('sku', sku)
            loader.add_value('identifier', pid)
            loader.add_value('brand', 'LEGO')
            loader.add_value('shipping_cost', 59)
            #if not stock:
                #loader.add_value('stock', 0)
            yield self.load_item_with_metadata(loader.load_item())
        else:
            self.errors.append("No price set for url: '%s'" % urljoin(base_url, response.url))
