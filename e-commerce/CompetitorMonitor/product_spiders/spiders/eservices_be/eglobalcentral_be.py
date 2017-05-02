# -*- coding: utf-8 -*-

import os
from product_spiders.spiders.eservicegroup_uk.eglobalcentral import EGlobalCentral


HERE = os.path.abspath(os.path.dirname(__file__))


class EGlobalCentralBeSpider(EGlobalCentral):
    name = "eglobalcentral_be"
    allowed_domains = ["eglobalcentral.be", "148.251.79.44", "searchanise.com"]
    search_url = 'http://www.eglobalcentral.be/product?subcats=Y&status=A&pshort=Y&pfull=Y&pname=Y&pkeywords=Y&search_performed=Y&hint_q=Rechercher%20des%20produits&items_per_page=200'
    data_file = os.path.join(HERE, 'eglobal.csv')
    searchanise_api = '0O7V3a9x3p'