from __future__ import absolute_import

import os
import io
import threading
import logging

import requests
import pandas as pd
from bs4 import BeautifulSoup

from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty, StringProperty, DictProperty, BooleanProperty
from kivy.app import App
from kivy.clock import Clock

from es_gui.apps.data_manager.data_manager import DATA_HOME
from es_gui.apps.data_manager.utils import check_connection_settings
from es_gui.resources.widgets.common import InputError, WarningPopup, ConnectionErrorPopup, MyPopup, RecycleViewRow, FADEIN_DUR, LoadingModalView, PALETTE, rgba_to_fraction, fade_in_animation
from es_gui.downloaders.building_data import get_commercial_geographical_locations, get_commercial_building_types, get_building_data, get_residential_load_types, get_residential_geographical_locations

MAX_WHILE_ATTEMPTS = 7

DATASET_ROOT = 'https://openei.org/datasets/files/961/pub/'
COMMERCIAL_LOAD_ROOT = DATASET_ROOT + 'COMMERCIAL_LOAD_DATA_E_PLUS_OUTPUT/'
RESIDENTIAL_LOAD_ROOT = DATASET_ROOT + 'RESIDENTIAL_LOAD_DATA_E_PLUS_OUTPUT/'


class DataManagerLoadHomeScreen(Screen):
    """"""
    def on_enter(self):
        ab = self.manager.nav_bar
        ab.build_data_manager_nav_bar()
        ab.set_title('Data Manager: Hourly Commercial/Residential Load Profiles')


class DataManagerCommercialLoadScreen(Screen):
    """"""
    connection_error_occurred = BooleanProperty(False)
    df_locations = pd.DataFrame()
    state_selected = StringProperty('')
    location_selected = DictProperty()
    building_selected = DictProperty()

    def __init__(self, **kwargs):
        super(DataManagerCommercialLoadScreen, self).__init__(**kwargs)

        StateRVEntry.host_screen = self
        LocationRVEntry.host_screen = self
        BuildingRVEntry.host_screen = self

    def on_enter(self):
        ab = self.manager.nav_bar
        ab.build_data_manager_nav_bar()
        ab.set_title('Data Manager: Hourly Commercial Load Profiles')

        StateRVEntry.host_screen = self
        LocationRVEntry.host_screen = self
        BuildingRVEntry.host_screen = self

        if self.df_locations.empty:
            logging.info('LoadProfileDM: Retrieving locations from database...')
            ssl_verify, proxy_settings = check_connection_settings()

            self._get_locations(ssl_verify, proxy_settings)

            # try:
            #     thread_locations = threading.Thread(target=self._get_locations, args=[ssl_verify, proxy_settings])
            #     thread_locations.start()
            # except requests.ConnectionError:
            #     popup = WarningPopup()
            #     popup.popup_text.text = 'There was an issue connecting to the profile database. Check your connection settings and try again.'
            #     popup.open()

    
    def on_connection_error_occurred(self, instance, value):
        if value:
            popup = ConnectionErrorPopup()
            popup.popup_text.text = 'There was an issue connecting to the profile database. Check your connection settings and try again.'
            popup.open()

    def _get_locations(self, ssl_verify=True, proxy_settings=None):
        self.connection_error_occurred = False

        locations, self.connection_error_occurred = get_commercial_geographical_locations(
            ssl_verify=ssl_verify, 
            proxy_settings=proxy_settings, 
            n_attempts=MAX_WHILE_ATTEMPTS
            )

        self.df_locations = pd.DataFrame.from_records(locations)

        # Populate state RecycleView.
        if self.df_locations.empty:
            return
        else: 
            records = [{'name': state} for state in self.df_locations['state'].unique()]
            records = sorted(records, key=lambda t: t['name'])

            self.state_rv.data = records
            self.state_rv.unfiltered_data = records

    def _get_building_types(self, location_root, ssl_verify=True, proxy_settings=None):
        self.connection_error_occurred = False

        building_types, self.connection_error_occurred = get_commercial_building_types(
            location_root,
            ssl_verify=ssl_verify,
            proxy_settings=proxy_settings,
            n_attempts=MAX_WHILE_ATTEMPTS
        )

        # Populate building types RecycleView.
        self.building_rv.data = building_types
        self.building_rv.unfiltered_data = building_types

    def on_state_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: State selection changed to {0}.'.format(value))
        except KeyError:
            logging.info('LoadProfileDM: State selection reset.')
        else:
            locations = self.df_locations.loc[self.df_locations['state'] == value]

            records = locations.to_dict(orient='records')
            records = [{'name': record['name'], 'link': record['link']} for record in records]
            records = sorted(records, key=lambda t: t['name'])

            self.location_rv.data = records
            self.location_rv.unfiltered_data = records
        finally:
            self.location_rv.deselect_all_nodes()
            self.location_rv_filter.text = ''
            self.location_selected = ''

    def on_location_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: Location selection changed to {0}.'.format(value['name']))
        except KeyError:
            logging.info('LoadProfileDM: Location selection reset.')
        else:
            location_root_link = value['link']

            ssl_verify, proxy_settings = check_connection_settings()

            self._get_building_types(location_root_link, ssl_verify, proxy_settings)

            # thread_building_types = threading.Thread(target=self._get_building_types, args=[location_root_link, ssl_verify, proxy_settings])
            # thread_building_types.start()
        finally:
            self.building_rv.deselect_all_nodes()
            self.building_rv_filter.text = ''
            self.building_selected = {}
            # self.building_rv.data = []
            # self.building_rv.unfiltered_data = []
    
    def on_building_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: Building type selection changed to {0}.'.format(value['name']))
        except KeyError:
            logging.info('LoadProfileDM: Building type selection reset.')
    
    def _validate_selections(self):
        csv_link = self.building_selected['link']

        return csv_link
    
    def save_load_data(self):
        """Saves the data for the building type selected."""
        try:
            csv_link = self._validate_selections()
        except Exception as e:
            print(e)
        else:
            ssl_verify, proxy_settings = check_connection_settings()

            self.connection_error_occurred = False

            url_split = csv_link.split('/')
            destination_dir = os.path.join(DATA_HOME, 'load', 'commercial', url_split[-2])
            os.makedirs(destination_dir, exist_ok=True)

            self.connection_error_occurred = get_building_data(
                csv_link,
                save_directory=destination_dir,
                ssl_verify=ssl_verify,
                proxy_settings=proxy_settings,
                n_attempts=MAX_WHILE_ATTEMPTS
            )

            if not self.connection_error_occurred:
                popup = WarningPopup()
                popup.title = 'Success!'
                popup.popup_text.text = 'Load data successfully saved.'
                popup.open()

                logging.info('LoadProfileDM: Load data successfully saved.')
            

class StateRVEntry(RecycleViewRow):
    host_screen = None

    def apply_selection(self, rv, index, is_selected):
        """Respond to the selection of items in the view."""
        super(StateRVEntry, self).apply_selection(rv, index, is_selected)

        if is_selected:
            self.host_screen.state_selected = rv.data[self.index]['name']


class LocationRVEntry(RecycleViewRow):
    host_screen = None

    def apply_selection(self, rv, index, is_selected):
        """Respond to the selection of items in the view."""
        super(LocationRVEntry, self).apply_selection(rv, index, is_selected)

        if is_selected:
            self.host_screen.location_selected = rv.data[self.index]


class BuildingRVEntry(RecycleViewRow):
    host_screen = None

    def apply_selection(self, rv, index, is_selected):
        """Respond to the selection of items in the view."""
        super(BuildingRVEntry, self).apply_selection(rv, index, is_selected)

        if is_selected:
            self.host_screen.building_selected = rv.data[self.index]


class DataManagerResidentialLoadScreen(Screen):
    """"""
    connection_error_occurred = BooleanProperty(False)
    df_locations = pd.DataFrame()
    load_type_selected = DictProperty()
    state_selected = StringProperty('')
    location_selected = DictProperty()

    def __init__(self, **kwargs):
        super(DataManagerResidentialLoadScreen, self).__init__(**kwargs)

        LoadTypeRVEntry.host_screen = self
        LocationRVEntry.host_screen = self
        StateRVEntry.host_screen = self

    def on_enter(self):
        ab = self.manager.nav_bar
        ab.build_data_manager_nav_bar()
        ab.set_title('Data Manager: Hourly Residential Load Profiles')

        LoadTypeRVEntry.host_screen = self
        LocationRVEntry.host_screen = self
        StateRVEntry.host_screen = self

        ssl_verify, proxy_settings = check_connection_settings()

        self._get_load_types(ssl_verify, proxy_settings)

        # thread_locations = threading.Thread(target=self._get_load_types, args=[ssl_verify, proxy_settings])
        # thread_locations.start()
    
    def on_connection_error_occurred(self, instance, value):
        if value:
            popup = ConnectionErrorPopup()
            popup.popup_text.text = 'There was an issue connecting to the profile database. Check your connection settings and try again.'
            popup.open()
    
    def _get_load_types(self, ssl_verify=True, proxy_settings=None):
        self.connection_error_occurred = False

        load_types, self.connection_error_occurred = get_residential_load_types(
            ssl_verify=ssl_verify,
            proxy_settings=proxy_settings,
            n_attempts=MAX_WHILE_ATTEMPTS
        )
        
        # Populate load types RecycleView.
        records = [{'name': load_type['name'], 'link': load_type['link']} for load_type in load_types]
        records = sorted(records, key=lambda t: t['name'])

        self.load_type_rv.data = records
        self.load_type_rv.unfiltered_data = records
    
    def _get_locations(self, load_root_link, ssl_verify=True, proxy_settings=None):
        self.connection_error_occurred = False

        locations, self.connection_error_occurred = get_residential_geographical_locations(
            load_root_link,
            ssl_verify=ssl_verify,
            proxy_settings=proxy_settings,
            n_attempts=MAX_WHILE_ATTEMPTS
        )

        self.df_locations = pd.DataFrame.from_records(locations)

        # Populate state RV.
        records = [{'name': state} for state in self.df_locations['state'].unique()]
        records = sorted(records, key=lambda t: t['name'])

        self.state_rv.data = records
        self.state_rv.unfiltered_data = records
    
    def on_load_type_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: Load type selection changed to {0}.'.format(value['name']))
        except KeyError:
            logging.info('LoadProfileDM: Load type selection reset.')
        else:
            load_type_root_link = value['link']

            ssl_verify, proxy_settings = check_connection_settings()

            self._get_locations(load_type_root_link, ssl_verify, proxy_settings)

            # thread_building_types = threading.Thread(target=self._get_locations, args=[load_type_root_link, ssl_verify, proxy_settings])
            # thread_building_types.start()
        finally:
            self.state_rv.deselect_all_nodes()
            self.state_rv_filter.text = ''
            self.state_selected = ''

    def on_state_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: State selection changed to {0}.'.format(value))
        except KeyError:
            logging.info('LoadProfileDM: State selection reset.')
        else:
            locations = self.df_locations.loc[self.df_locations['state'] == value]

            records = locations.to_dict(orient='records')
            records = [{'name': record['name'], 'link': record['link']} for record in records]
            records = sorted(records, key=lambda t: t['name'])

            self.location_rv.data = records
            self.location_rv.unfiltered_data = records
        finally:
            self.location_rv.deselect_all_nodes()
            self.location_rv_filter.text = ''
            self.location_selected = ''

    def on_location_selected(self, instance, value):
        try:
            logging.info('LoadProfileDM: Location selection changed to {0}.'.format(value['name']))
        except KeyError:
            logging.info('LoadProfileDM: Location selection reset.')
    
    def _validate_selections(self):
        csv_link = self.location_selected['link']

        return csv_link
    
    def save_load_data(self):
        """Saves the data for the building type selected."""
        try:
            csv_link = self._validate_selections()
        except Exception as e:
            print(e)
        else:
            ssl_verify, proxy_settings = check_connection_settings()

            self.connection_error_occurred = False

            url_split = csv_link.split('/')
            destination_dir = os.path.join(DATA_HOME, 'load', 'residential', url_split[-2])
            os.makedirs(destination_dir, exist_ok=True)

            self.connection_error_occurred = get_building_data(
                csv_link,
                save_directory=destination_dir,
                ssl_verify=ssl_verify,
                proxy_settings=proxy_settings,
                n_attempts=MAX_WHILE_ATTEMPTS
            )

            if not self.connection_error_occurred:
                popup = WarningPopup()
                popup.title = 'Success!'
                popup.popup_text.text = 'Load data successfully saved.'
                popup.open()

                logging.info('LoadProfileDM: Load data successfully saved.')
    

class LoadTypeRVEntry(RecycleViewRow):
    host_screen = None

    def apply_selection(self, rv, index, is_selected):
        """Respond to the selection of items in the view."""
        super(LoadTypeRVEntry, self).apply_selection(rv, index, is_selected)

        if is_selected:
            self.host_screen.load_type_selected = rv.data[self.index]