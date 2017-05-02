import os

from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request, HtmlResponse, FormRequest
from scrapy.utils.response import get_base_url
from scrapy.utils.url import urljoin_rfc
from product_spiders.items import Product, ProductLoaderWithNameStrip as ProductLoader

HERE = os.path.abspath(os.path.dirname(__file__))


class portonaquapet_spider(BaseSpider):
    name = 'portonaquapet.co.uk'
    allowed_domains = ['portonaquapet.co.uk', 'www.portonaquapet.co.uk']
    start_urls = ('http://www.portonaquapet.co.uk/',)

    def parse(self, response):
        if not isinstance(response, HtmlResponse):
            return
        hxs = HtmlXPathSelector(response)

        # categories
        categories = hxs.select(u'//div[@id="ctl00_menu_products_pnlsmenu"]//a/@href').extract()
        for url in categories:
            url = urljoin_rfc(get_base_url(response), url)
            yield Request(url)

        subcategories = hxs.select(u'//div[@class="item"]//a/@href').extract()
        for url in subcategories:
            url = urljoin_rfc(get_base_url(response), url)
            yield Request(url)

        # pagination
        next_page = hxs.select(u'//a[@class="next i-next"]/@href').extract()
        if next_page:
            next_page = urljoin_rfc(get_base_url(response), next_page[0])
            yield Request(next_page)

        # products
        products = hxs.select(u'//div[@class="item product-box "]//a/@href').extract()
        for url in products:
            url = urljoin_rfc(get_base_url(response), url)
            yield Request(url, callback=self.parse_product)

    def parse_product(self, response):
        if not isinstance(response, HtmlResponse):
            return
        hxs = HtmlXPathSelector(response)

        name = hxs.select(u'//div[@class="datac2"]//h1[@class="mpv_desc"]/text()').extract()[0].strip()
        multiple_options = hxs.select(u'//select[@class="mpv_itemalst"]//option')
        if multiple_options and not u'requested' in response.meta:
            for option in multiple_options:
                formname = u'aspNetForm'
                formdata = {u'ctl00$MainContent$ItemAList' : option.select(u'./@value').extract()[0],
                            u'__EVENTTARGET' : u'ctl00$MainContent$ItemAList',
                            u'__EVENTARGUMENT' : u''}
                req = FormRequest.from_response(response, formname=formname,
                                                    formdata=formdata,
                                                    meta={u'requested': True},
                                                    dont_click=True, callback=self.parse_product)
                yield req
        if multiple_options:
            name += u' %s' % multiple_options.select(u'../option[@selected]/text()').extract()[0].strip()

        loader = ProductLoader(item=Product(), response=response)

        product_id = hxs.select('//*[@id="ctl00_MainContent_lblLinecode"]/text()').re(r'(\d+)')
        if product_id:
            loader.add_value('identifier', product_id[0])
        else:
            self.log('ERROR: Identifier not found!')

        product_sku = hxs.select('//*[@id="ctl00_MainContent_lblProductCode"]/text()').re(r'(\d+)')
        if product_sku:
            loader.add_value('sku', product_sku[0])
        else:
            self.log('ERROR: SKU not found!')

        product_image = hxs.select('//*[@id="zoom1"]/@href').extract()
        if product_image:
            url = urljoin_rfc(get_base_url(response), product_image[0])
            loader.add_value('image_url', url)

        product_category = hxs.select('//*[@id="papertrail"]/ul/li[1]/a/text()').extract()
        if product_category:
            loader.add_value('category', product_category[0])

        loader.add_value('url', response.url)
        loader.add_value('name', name)
        loader.add_xpath('price', u'//div[@class="datac2"]//span[@class="offerprc"]/text()')
        if not loader.get_output_value('price'):
            loader.add_xpath('price', u'//span[@class="mpv_prc"]/text()')
        if loader.get_output_value('price'):
            yield loader.load_item()