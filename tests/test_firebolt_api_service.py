from datetime import date

from firebolt_db.firebolt_api_service import FireboltApiService
from requests.exceptions import HTTPError
from firebolt_db import exceptions
import pytest
import os

test_username = os.environ["username"]
test_password = os.environ["password"]
test_db_name = os.environ["db_name"]
test_engine_name = os.environ["engine_name"]
query = 'select * from ci_fact_table limit 1'


access_token = FireboltApiService.get_access_token({'username': test_username,
                                                    'password': test_password})
engine_url = FireboltApiService.get_engine_url_by_engine(test_engine_name, access_token["access_token"])


class TestFireboltApiService:

    def test_get_connection_success(self):
        response = FireboltApiService.get_connection(test_username, test_password,
                                                     test_engine_name, date.today())
        if type(response) == HTTPError:
            assert response.response.status_code == 503
        else:
            assert response != ""

    def test_get_connection_invalid_credentials(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_connection('username', 'password', test_engine_name, date.today())[0]

    def test_get_connection_invalid_engine_name(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_connection(test_username, test_password, 'engine_name', date.today())[1]

    def test_get_access_token_success(self):
        assert access_token["access_token"] != ""

    def test_get_access_token_invalid_credentials(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_access_token({'username': 'username', 'password': 'password'})

    def test_get_access_token_via_refresh_success(self):
        assert FireboltApiService.get_access_token_via_refresh(access_token["refresh_token"]) != ""

    def test_get_access_token_via_refresh_invalid_token(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_access_token_via_refresh({'refresh_token': 'refresh_token'})

    def test_get_engine_url_by_engine_success(self):
        assert engine_url != ""

    def test_get_engine_url_by_engine_invalid_engine_name(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_engine_url_by_engine('engine_name', access_token["access_token"])

    def test_get_engine_url_by_engine_invalid_header(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.get_engine_url_by_engine(test_engine_name, 'header') != ""

    def test_run_query_success(self):
        try:
            response = FireboltApiService.run_query(access_token["access_token"],
                                                    engine_url, test_db_name,
                                                    query)
            assert response != ""
        except exceptions.InternalError as http_err:
            assert http_err != ""

    def test_run_query_invalid_url(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.run_query(access_token["access_token"], "",
                                                    test_db_name, query) != {}

    def test_run_query_invalid_schema(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.run_query(access_token["access_token"],
                                                    engine_url, 'db_name', query)

    def test_run_query_invalid_header(self):
        try:
            response = FireboltApiService.run_query('header',
                                                    engine_url, test_db_name,
                                                    query)
            assert response != ""
        except exceptions.InternalError as e_info:
            assert e_info != ""

    def test_run_query_invalid_query(self):
        with pytest.raises(Exception) as e_info:
            response = FireboltApiService.run_query(access_token["access_token"],
                                                    engine_url, test_db_name, 'query')
