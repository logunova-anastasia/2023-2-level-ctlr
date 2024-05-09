"""
Crawler implementation.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable
import datetime
import json
import pathlib
import re
import shutil
from random import randrange
from time import sleep
from typing import Pattern, Union

import requests
from bs4 import BeautifulSoup

from core_utils.article.article import Article
from core_utils.article.io import to_meta, to_raw
from core_utils.config_dto import ConfigDTO
from core_utils.constants import ASSETS_PATH, CRAWLER_CONFIG_PATH


class IncorrectSeedURLError(Exception):
    """
    Seed URL does not match standard pattern
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    Total number of articles is out of range from 1 to 150
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    Total number of articles to parse is not positive integer
    """


class IncorrectHeadersError(Exception):
    """
    Headers are not in a form of dictionary
    """


class IncorrectEncodingError(Exception):
    """
    Encoding is not a string
    """


class IncorrectTimeoutError(Exception):
    """
    Timeout value is not a positive integer less than 60
    """


class IncorrectVerifyError(Exception):
    """
    Verify certificate value is not True or False
    """


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self.config_dto = self._extract_config_content()
        self._validate_config_content()

        self._seed_urls = self.config_dto.seed_urls
        self._headers = self.config_dto.headers
        self._num_articles = self.config_dto.total_articles
        self._encoding = self.config_dto.encoding
        self._timeout = self.config_dto.timeout
        self._should_verify_certificate = self.config_dto.should_verify_certificate
        self._headless_mode = self.config_dto.headless_mode

    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as file:
            config = json.load(file)

        return ConfigDTO(**config)

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        if not isinstance(self.config_dto.seed_urls, list):
            raise IncorrectSeedURLError

        for seed_url in self.config_dto.seed_urls:
            if not re.match(r"https?://(www.)?scientificrussia\.ru/news", seed_url):
                raise IncorrectSeedURLError

        if not isinstance(self.config_dto.total_articles, int) or \
                self.config_dto.total_articles <= 0:
            raise IncorrectNumberOfArticlesError

        if not 0 < self.config_dto.total_articles < 150:
            raise NumberOfArticlesOutOfRangeError

        if not isinstance(self.config_dto.headers, dict):
            raise IncorrectHeadersError

        if not isinstance(self.config_dto.encoding, str):
            raise IncorrectEncodingError

        if not isinstance(self.config_dto.timeout, int) or not 0 <= self.config_dto.timeout < 60:
            raise IncorrectTimeoutError

        if not isinstance(self.config_dto.should_verify_certificate, bool) or not isinstance(
                self.config_dto.headless_mode, bool):
            raise IncorrectVerifyError

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self._headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    sleep(randrange(2))
    return requests.get(url=url, headers=config.get_headers(),
                        timeout=config.get_timeout(), verify=config.get_verify_certificate())


class Crawler:
    """
    Crawler implementation.
    """

    url_pattern: Union[Pattern, str]

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        self.config = config
        self.urls = []
        self.url_pattern = 'https://scientificrussia.ru'

    def _extract_url(self, article_bs: BeautifulSoup) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.BeautifulSoup): BeautifulSoup instance

        Returns:
            str: Url from HTML
        """
        return self.url_pattern + str(article_bs.find('a').get('href')) \
            if article_bs.find('a').get('href') else ''

    def find_articles(self) -> None:
        """
        Find articles.
        """
        for url in self.get_search_urls():
            response = make_request(url, self.config)

            if not response.ok:
                continue

            soup = BeautifulSoup(response.text, 'lxml')
            for div in soup.find(class_="card-body").find_all("div", {"class": "title"}):
                if self._extract_url(div) and self._extract_url(div) not in self.urls:
                    self.urls.append(self._extract_url(div))

                if len(self.urls) >= self.config.get_num_articles():
                    return

    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.config.get_seed_urls()


# 10
# 4, 6, 8, 10


class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(self.full_url, self.article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        text = article_soup.find(itemprop="articleBody")

        paragraphs = text.find_all('p')
        texts = [p.text for p in paragraphs]

        self.article.text = '\n'.join(texts)

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        author = article_soup.find(class_="props distant").find_all(class_='author')

        if author:
            self.article.author = [' '.join(i.text.split()[1:]) for i in author]
        else:
            self.article.author = ["NOT FOUND"]

        title = article_soup.find(itemprop="name headline")

        if title:
            self.article.title = title.text.strip()

        date = article_soup.find('time').text
        self.article.date = self.unify_date_format(date)

        list_of_keywords = []
        keywords = article_soup.find_all(itemprop="keywords")

        for i in keywords:
            list_of_keywords.append(i.text)

        self.article.topics = list_of_keywords

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        return datetime.datetime.strptime(date_str, '%d.%m.%Y %H:%M')

    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """
        response = make_request(self.full_url, self.config)

        if response.ok:
            article_bs = BeautifulSoup(response.text, 'lxml')
            self._fill_article_with_text(article_bs)
            self._fill_article_with_meta_information(article_bs)
        return self.article


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)


class CrawlerRecursive(Crawler):
    """
    Recursive Crawler implementation
    """
    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        super().__init__(config)
        self.start_url = self.config.get_seed_urls()[0]
        self.urls = []
        self.possible_urls = [self.start_url]
        self.path = ASSETS_PATH.parent / 'recursive_crawler.json'
        self.visited_urls = []
        self.created_articles = []
        self.get_info()

    def get_info(self) -> None:
        """
        Get information about the crawler from a file.
        """
        if not self.path.exists():
            shutil.rmtree(ASSETS_PATH)
            return

        with open(self.path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        self.urls = data['urls']
        self.possible_urls = data['possible_urls']
        self.visited_urls = data['visited_urls']
        self.created_articles = data['created_articles']

    def save_info(self) -> None:
        """
        Save information about the crawler.
        """
        data = {
            'urls': self.urls,
            'number of collected urls': len(self.urls),
            'possible_urls': self.possible_urls,
            'visited_urls': self.visited_urls,
            'created_articles': self.created_articles
        }
        if not ASSETS_PATH.exists():
            ASSETS_PATH.mkdir(parents=True)

        with open(self.path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)

    def find_articles(self) -> None:
        """
        Find articles.
        """
        url = self.possible_urls[len(self.visited_urls)]

        if url not in self.visited_urls:
            self.visited_urls.append(url)

        response = make_request(url, self.config)

        if not response.ok:
            return

        article_bs = BeautifulSoup(response.text, 'lxml')

        links = article_bs.find_all('a')
        articles = []

        for div in article_bs.find(class_="card-body").find_all("div", {"class": "title"}):
            articles.append(self._extract_url(div))

        for i in links:
            if not i.get('href'):
                continue

            if 'https' in i.get('href'):
                link_url = i.get('href')
            else:
                link_url = self.url_pattern + i.get('href')

            if link_url not in self.possible_urls:
                self.possible_urls.append(link_url)
            if link_url not in self.urls and link_url in articles:
                self.urls.append(link_url)

            self.save_info()

            if len(self.urls) >= self.config.get_num_articles():
                return

        self.find_articles()


def main() -> None:
    """
    Entrypoint for scrapper module.
    """
    conf = Config(CRAWLER_CONFIG_PATH)
    crawler = Crawler(conf)
    crawler.find_articles()
    prepare_environment(ASSETS_PATH)

    for id_num, url in enumerate(crawler.urls, 1):
        parser = HTMLParser(url, id_num, conf)
        article = parser.parse()
        if isinstance(article, Article):
            to_raw(article)
            to_meta(article)


def recursive_main() -> None:
    """
    Entrypoint for recursive scrapper module.
    """
    conf = Config(CRAWLER_CONFIG_PATH)

    crawler = CrawlerRecursive(conf)
    crawler.find_articles()

    for id_num, url in enumerate(crawler.urls, 1):
        if url not in crawler.created_articles:
            parser = HTMLParser(url, id_num, conf)
            article = parser.parse()
            if isinstance(article, Article):
                to_raw(article)
                to_meta(article)
            crawler.created_articles.append(url)
            crawler.save_info()


if __name__ == "__main__":
    recursive_main()
