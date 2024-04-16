"""
Crawler implementation.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable
import json
import pathlib
import re
import requests
from bs4 import BeautifulSoup
from core_utils.article.io import to_raw
from core_utils.constants import CRAWLER_CONFIG_PATH, ASSETS_PATH
from core_utils.article.article import Article
from core_utils.config_dto import ConfigDTO
from random import randrange
from time import sleep
from typing import Pattern, Union


class IncorrectSeedURLError(Exception):
    pass


class NumberOfArticlesOutOfRangeError(Exception):
    pass


class IncorrectNumberOfArticlesError(Exception):
    pass


class IncorrectHeadersError(Exception):
    pass


class IncorrectEncodingError(Exception):
    pass


class IncorrectTimeoutError(Exception):
    pass


class IncorrectVerifyError(Exception):
    pass


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

        return ConfigDTO(
            seed_urls=config["seed_urls"],
            total_articles_to_find_and_parse=config["total_articles_to_find_and_parse"],
            headers=config["headers"],
            encoding=config["encoding"],
            timeout=config["timeout"],
            should_verify_certificate=config["should_verify_certificate"],
            headless_mode=config["headless_mode"])

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        if not isinstance(self.config_dto.seed_urls, list):
            raise IncorrectSeedURLError

        for seed_url in self.config_dto.seed_urls:
            if not re.match(r"https?://(www.)?", seed_url):
                raise IncorrectSeedURLError

        if not isinstance(self.config_dto.total_articles, int) or self.config_dto.total_articles <= 0:
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
    sleep(randrange(5))
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
        url = ''
        for div in article_bs.find_all("div", {"class": "title"}, limit=24):
            for link in div.select("a"):
                url = link['href']
        return self.url_pattern + url

    def find_articles(self) -> None:
        """
        Find articles.
        """
        urls = []

        for url in self.get_search_urls():
            response = make_request(url, self.config)

            if not response.ok:
                continue

            src = response.text
            soup = BeautifulSoup(src, 'lxml')
            urls.append(self._extract_url(soup))

        self.urls.extend(urls)

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
        text = article_soup.find_all(style="text-align: justify;")
        article = ''
        for paragraph in text:
            article += paragraph.text
        self.article.text = article

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        author = [' '.join(article_soup.find(class_='author').text.split()[1:])]
        if author:
            self.article.author = author
        else:
            self.article.author = ["NOT FOUND"]
        self.article.title = article_soup.find(itemprop="name headline").text.strip()

    # def unify_date_format(self, date_str: str) -> datetime.datetime:
    #     """
    #     Unify date format.
    #
    #     Args:
    #         date_str (str): Date in text format
    #
    #     Returns:
    #         datetime.datetime: Datetime object
    #     """

    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """
        response = make_request(self.full_url, self.config)
        src = response.text
        article_bs = BeautifulSoup(src, 'lxml')
        self._fill_article_with_text(article_bs)
        self._fill_article_with_meta_information(article_bs)

        return self.article


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """
    if not base_path.exists():
        base_path.mkdir()
    base_path.rmdir()
    base_path.mkdir()


def main() -> None:
    """
    Entrypoint for scrapper module.
    """
    conf = Config(CRAWLER_CONFIG_PATH)
    crawler = Crawler(conf)
    crawler.find_articles()
    prepare_environment(ASSETS_PATH)

    for id_num, url in enumerate(crawler.get_search_urls()):
        parser = HTMLParser(url, id_num, conf)
        article = parser.parse()
        if isinstance(article, Article):
            to_raw(article)


if __name__ == "__main__":
    main()
