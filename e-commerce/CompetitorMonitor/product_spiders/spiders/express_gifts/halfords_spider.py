import re
import os
import csv
import paramiko

import urllib

from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request, HtmlResponse
from scrapy.utils.response import get_base_url
from scrapy.utils.url import urljoin_rfc

from scrapy import log

from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader
from product_spiders.config import CLIENTS_SFTP_HOST, CLIENTS_SFTP_PORT

HERE = os.path.abspath(os.path.dirname(__file__))


class HalfordsSpider(BaseSpider):
    name = 'expressgifts-halfords.com'
    allowed_domains = ['halfords.com']

    start_urls = ['http://www.halfords.com']

    def parse(self, response):
        base_url = get_base_url(response)

        transport = paramiko.Transport((CLIENTS_SFTP_HOST, CLIENTS_SFTP_PORT))
        password = "jqh3aMrK"
        username = "expressgifts"
        transport.connect(username = username, password = password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        files = sftp.listdir_attr()
        
        file_path = HERE + '/express_gifts_flat_file.csv'
        sftp.get('express_gifts_flat_file.csv', file_path)


        with open(file_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row['HALFORDS'].strip()
                if url:
                    yield Request(url, callback=self.parse_product, meta={'row': row})

    def parse_product(self, response):
        hxs = HtmlXPathSelector(response)

        row = response.meta['row']

        try:
            category = hxs.select('//nav[@id="breadcrumb"]//ul/li/a/text()').extract()[1:]
        except IndexError:
            category = ''
        image_url = hxs.select('//div[@id="productImage"]//img[@id="fullImage"]/@src|//div[@id="productMainImage"]//img/@src').extract()
        if not image_url:
            image_url = hxs.select('//img[@id="tempImage"]/@src').extract()
        brand = hxs.select('//div[@class="hproduct"]/span[@class="brand"]/text()').extract()


        product_loader = ProductLoader(item=Product(), selector=hxs)
        product_loader.add_value('identifier', row['PRODUCT_NUMBER'])
        product_loader.add_value('sku', row['PRODUCT_NUMBER'])
        product_loader.add_xpath('name', '//h1[@class="productDisplayTitle"]/text()')
        price = hxs.select('//div[@id="priceAndLogo"]/h2/text()').re(r'[\d,.]+')
        product_loader.add_value('price', price[0])
        product_loader.add_value('url', response.url)
        product_loader.add_value('category', category)
        product_loader.add_value('image_url', image_url)
        product_loader.add_value('brand', brand)
        if product_loader.get_output_value('price')<30:
            product_loader.add_value('shipping_cost', 2.99)
        yield product_loader.load_item()	
