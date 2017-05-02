"""
Kitbag US account
Man Utd Store spider
Ticket link: https://app.assembla.com/spaces/competitormonitor/tickets/4941
"""
import os
import re
import csv
import json
from decimal import Decimal
import paramiko

from scrapy.spider import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy import Request, FormRequest

from product_spiders.items import Product, ProductLoaderWithoutSpaces as ProductLoader
from product_spiders.utils import extract_price

from product_spiders.config import CLIENTS_SFTP_HOST, CLIENTS_SFTP_PORT

HERE = os.path.abspath(os.path.dirname(__file__))


class ManUtdStore(CrawlSpider):
    name = 'kitbag_us-manutdstore'
    allowed_domains = ['store.manutd.com']
    start_urls = ['http://store.manutd.com/stores/manutd/us/c/football-kits?cur=USD',
                  'http://store.manutd.com/stores/manutd/us/c/fashion?cur=USD',
                  'http://store.manutd.com/stores/manutd/us/c/equipment?cur=USD']

    exchange_rate = None
    free_delivery_over = None
    shipping_cost = None

    categories = LinkExtractor(restrict_css='.facetCategory, .nav-menu-kit')
    products = LinkExtractor(restrict_css='.productListLink')

    rules = (
        Rule(categories, callback='parse_list', follow=True),
        Rule(products, callback='parse_product')
        )

    def start_requests(self):
        transport = paramiko.Transport((CLIENTS_SFTP_HOST, CLIENTS_SFTP_PORT))
        password = 'gtX34aJy'
        username = 'kitbag'
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        file_path = os.path.join(HERE, 'ExchangeRates.csv')
        sftp.get('Exchange Rates/Exchange Rates.csv', file_path)

        with open(file_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Currency'] == 'GBP-USD':
                    self.exchange_rate = extract_price(row['Rate'])
                    break

        self.log('Exchange rate: 1 GBP -> {} USD'.format(self.exchange_rate))
        yield Request('http://store.manutd.com/stores/manutd/en/product/manchester-united-sash-football---red-white-black---size-5/184083?cur=USD',
                      callback=self.parse_shipping)

    def parse_shipping(self, response):
        free_delivery_over = response.xpath('//ul[@class="uspContent"]/li/text()').re(u'Free Standard Delivery over \xa3(.*)')
        if free_delivery_over and self.exchange_rate:
            self.free_delivery_over = extract_price(free_delivery_over[0]) * self.exchange_rate
            self.log('Free delivery over {} USD'.format(self.free_delivery_over))
        else:
            self.free_delivery_over = 0
        formdata = {}
        formdata['__VIEWSTATEGENERATOR'] = response.xpath('//input[@name="__VIEWSTATEGENERATOR"]/@value').extract()[0]
        formdata['__EVENTVALIDATION'] = response.xpath('//input[@name="__EVENTVALIDATION"]/@value').extract()[0]
        formdata['__VIEWSTATE'] = response.xpath('//input[@name="__VIEWSTATE"]/@value').extract()[0]
        formdata['__EVENTTARGET'] = ''
        formdata['ctl00$ScriptManager1'] = ''
        formdata['ctl00$ContentMain$product_details1$dd_quantity'] = '1'
        formdata['ctl00$ContentMain$product_details1$imgbtn_addToBasket.x'] = '0'
        formdata['ctl00$ContentMain$product_details1$imgbtn_addToBasket.y'] = '0'

        req = FormRequest.from_response(response, formname='aspnetForm', formdata=formdata,
                                        callback=self.parse_shipping1)
        yield req

    def parse_shipping1(self, response):
        req = Request("http://store.manutd.com/stores/manutd/en/basket/basket?cur=USD",
                      dont_filter=True,
                      callback=self.parse_shipping2)
        yield req

    def parse_shipping2(self, response):
        shipping_cost = response.xpath('//select[contains(@id, "shippingMethods")]/option/text()').re('(\d+\.\d+)')
        try:
            self.shipping_cost = extract_price(shipping_cost[0])
            self.logger.info('Shipping cost is %s' % self.shipping_cost)
        except IndexError:
            self.logger.error('No shipping cost parsed from basket. Spider will be closed')
        for url in self.start_urls:
            yield Request(url)


    def parse_list(self, response):
        formdata = {'__EVENTARGUMENT': '',
                    '__EVENTTARGET': 'ctl00$ContentMain$product_browse1$lv_pagingTop$lb_viewAll'}
        if response.css('.pages a'):
            yield FormRequest.from_response(response, formdata=formdata)

    def parse_product(self, response):
        if 'aspxerrorpath' in response.url:
            yield Request(response.request.meta['redirect_urls'][0], self.parse_product, dont_filter=True)
        base_product = True
        add_custom_personalization = False
        loader = ProductLoader(item=Product(), response=response)
        loader.add_xpath('url', '//link[@rel="canonical"]/@href')
        loader.add_value('category', 'Jerseys')
        heros_data = response.xpath('//script/text()').re('product\d{7} =(.+?});var')
        base_product_data = response.xpath('//script/text()').re('product\w{6} =(.+?});var')
        if not base_product_data:
            for p in self.parse(response):
                yield p
            return
        if not heros_data:
            data = json.loads(base_product_data[0])
        elif len(heros_data) == 1:
            data = json.loads(heros_data[0])
            base_product = False
        else:
            data = [json.loads(x) for x in heros_data]
            data = {x['ProductID']: x for x in data}
            heros = response.css('select.heroShirts')
            hero = heros.xpath('option[@selected]')
            if not hero:
                data = json.loads(base_product_data[0])
            else:
                data = data[int(hero.xpath('@value').extract_first())]
                base_product = False
                
        base_product_data = json.loads(base_product_data[0])
        
        #Checking custom personalization
        printings = {p['PrintingTypeID']: p for p in base_product_data['printingitems']}
        custom_printings = printings.get(1)
        if custom_printings and base_product:
            add_custom_personalization = True
            
        loader.add_value('name', data['Description'])
        loader.add_xpath('sku', '//script/text()', re='sku":"(.+?)"')
        if data['Brand']:
            loader.add_value('brand', data['Brand']['Name'])
        loader.add_value('image_url', response.urljoin(data['ImageURL']))
        product = loader.load_item()
        player_from_name = re.search('(?!Sponsor).*with *([\w\ \.\-]+?) (\d+)', data.get('Description', ''), re.UNICODE)
        if player_from_name:
            player_name, number = player_from_name.groups()
            
        #sizes
        for variation in data['Variations']:
            size = variation['Description']
            loader = ProductLoader(item=Product(), response=response)
            loader.add_value(None, product)
            loader.replace_value('identifier', variation['VariationId'])
            loader.add_value('name', size)
            loader.replace_value('price', variation['PriceActual'])
            if variation['PriceActual'] < self.free_delivery_over:
                loader.replace_value('shipping_cost', self.shipping_cost)
            loader.replace_value('stock', int(variation['IsInStock']))
            item = loader.load_item()
            if player_from_name:
                item['metadata'] = {'player': player_name, 'number': number, 'size': size}
            else:
                item['metadata'] = {'size': size}
            yield item
            base_size_items = [item]

            #Custom printings
            if add_custom_personalization:
                team_player_name = 'WILLIAMS'
                team_player_number = '10'
                team_player_id = 'WILLIAMS'
                loader = ProductLoader(item=Product(), response=response)
                loader.add_value(None, item)
                loader.add_value('name', team_player_name)
                loader.add_value('name', team_player_number)
                price = Decimal(item['price']) + Decimal(str(custom_printings['PriceActual']))
                loader.replace_value('price', price)
                if price >= self.free_delivery_over:
                    loader.replace_value('shipping_cost', 0)
                identifier = '-'.join((item['identifier'],
                                        str(custom_printings['PrintingID']),
                                        team_player_id))
                loader.replace_value('identifier', identifier)
                custom_item = loader.load_item()
                custom_item['metadata'] = {'player': team_player_name,
                                            'number': team_player_number,
                                            'size': size}
                yield custom_item
                base_size_items.append(custom_item)
            
            #Badges
            printing = printings.get(3)
            if not printing:
                continue
            for base_item in base_size_items:
                loader = ProductLoader(item=Product(), response=response)
                loader.add_value(None, base_item)
                loader.add_value('name', printing['PrintingDescription'])
                price = Decimal(base_item['price']) + Decimal(str(printing['PriceActual']))
                loader.replace_value('price', price)
                if price >= self.free_delivery_over:
                    loader.replace_value('shipping_cost', 0)
                identifier = base_item['identifier'] + '-' + str(printing['PrintingID'])
                loader.replace_value('identifier', identifier)
                badge_item = loader.load_item()
                badge_item['metadata'] = base_item['metadata'].copy()
                yield badge_item
