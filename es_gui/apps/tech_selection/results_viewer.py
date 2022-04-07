from __future__ import absolute_import

import os
import matplotlib.pyplot as plt
import pandas as pd
from es_gui.apps.tech_selection import fAux

from kivy.app import App
from kivy.uix.screenmanager import Screen

from es_gui.resources.widgets.common import BASE_TRANSITION_DUR, WarningPopup, stnd_font
from es_gui.apps.tech_selection import fPlots
#from es_gui.apps.tech_selection.analysis import perform_tech_selection


class TechSelectionFeasible(Screen):
    """"""
    def __init__(self, **kwargs):
        super(TechSelectionFeasible, self).__init__(**kwargs)

    def on_pre_enter(self):
        """Clear any widgets already present in the screen and create a new widget displaying the user selections."""
        if self.param_widget.children:
            self.param_widget.clear_widgets()
        self.param_widget.build()

        for child in self.param_widget.children:
            child.name.font_size, child.text_input.font_size = stnd_font, stnd_font
            child.name.size_hint_x, child.text_input.size_hint_x = 0.35, 0.65

        self.plot_feasibility_image.reload()
        # # """Clear any widgets already present in the screen and create a new widget displaying the user selections."""
        # # if self.plot_feasibility.children:
            # # self.plot_feasibility.clear_widgets()
        # #self.plot_feasibility.build()

    def _next_screen(self):
        if not self.manager.has_screen('ranking_techs'):
            screen = TechSelectionRanking(name='ranking_techs')
            self.manager.add_widget(screen)

        self.manager.transition.duration = BASE_TRANSITION_DUR
        self.manager.transition.direction = 'left'
        self.manager.current = 'ranking_techs'


class TechSelectionRanking(Screen):
    """"""
    def __init__(self, **kwargs):
        super(TechSelectionRanking, self).__init__(**kwargs)

    def on_pre_enter(self):
        """Clear any widgets already present in the screen and create a new widget displaying the user selections."""

        # Collect user selections values from a .json file
        data_manager = App.get_running_app().data_manager
        MODEL_PARAMS = data_manager.get_tech_selection_params()
        user_selections = {val['attr name']: val['value'] for val in MODEL_PARAMS}

        self.target_cost_kW = 1500
        self.target_cost_kWh = 1000

        if user_selections['app_type'] == 'Energy':
            self.togglebutton_kWh.state = 'down'
            self.togglebutton_kW.state = 'normal'
            self.target_cost_value.text = str(self.target_cost_kWh)
        elif user_selections['app_type'] == 'Power':
            self.togglebutton_kWh.state = 'normal'
            self.togglebutton_kW.state = 'down'
            self.target_cost_value.text = str(self.target_cost_kW)
        else:
            pass

        self.dfRanking = pd.read_csv(os.path.join('results', 'tech_selection', 'table_ranking.csv'), index_col=0)

        if self.param_widget.children:
            self.param_widget.clear_widgets()
        self.param_widget.build()

        for child in self.param_widget.children:
            child.name.font_size, child.text_input.font_size = stnd_font, stnd_font
            child.name.size_hint_x, child.text_input.size_hint_x = 0.35, 0.65

        self.plot_ranking_image.reload()

    def help_weights(self):
        """"""
        popup = WarningPopup(size_hint=(0.5, 0.5))
        popup.title = 'Weights for each category'
        popup.popup_text.text = (
            'The total feasibility score for each energy storage technology is given as the weighted geometric mean of the '
            'four individual scores (application, location, cost, and maturity).\n\nBy default, all categories have the '
            'same weight. However, the user can modify the weights to prioritize a subset of these categories.\n\nSetting '
            'a weight to 0.0 effectively removes the corresponding category from the final computation.'
            )
        popup.open()


    def help_target_cost(self):
        """"""
        popup = WarningPopup(size_hint=(0.5, 0.45))
        popup.title = 'Target cost'
        popup.popup_text.text = (
            'The cost score for each energy storage technology is inversely proportional to its total capital cost and '
            'normalized with respect to a desirable target cost.\n\nAt a given target cost, the cost score is 0.5.\n\nThe '
            'target cost is usually given in $/kW for power applications and in $/kWh for energy applications.'
            )
        popup.open()

    def update_scores(self):
        """"""

        test_aux = pd.DataFrame(self.dfRanking[['Application score', 'Location score', 'Cost score', 'Maturity score']])

        xx = test_aux['Cost score'].values
        old_target = 1500
        new_target = float(self.target_cost_value.text)
        #bb = new_target / (old_target*(1-xx)/xx + new_target)
        bb = new_target*xx / (old_target*(1-xx) + new_target*xx) # Avoid "division by zero" warnings
        test_aux['Cost score'] = bb
        self.dfRanking['Cost score'] = bb

        self.dfRanking['Total score'] = fAux.geom_mean(test_aux, weights=[self.app_slider.value, self.location_slider.value, self.cost_slider.value, self.maturity_slider.value])
        self.dfRanking.fillna(value=0, inplace=True)
        self.dfRanking.sort_values(by=['Total score', 'Application score', 'Location score', 'Cost score', 'Maturity score'], inplace=True)

        # Plot: final feasibility scores
        fig = fPlots.plot_ranking_techs(self.dfRanking)
        fig.savefig(os.path.join('results', 'tech_selection', 'plot_ranking.png'))

        self.plot_ranking_image.reload()

        type_of_cost = [tb.text for tb in [self.togglebutton_kW, self.togglebutton_kWh] if tb.state == 'down'][0]

        popup = WarningPopup(size_hint=(0.4, 0.4))
        popup.title = 'Success!'
        popup.popup_text.text = (
            f'The total feasibility score has been recomputed with the following settings:\n\n'
            f'- Weights: {self.app_slider.value:.2f} (application), {self.location_slider.value:.2f} (location), '
            f'{self.cost_slider.value:.2f} (cost), and {self.maturity_slider.value:.2f} (maturity).\n'
            f'- Target cost: {self.target_cost_value.text} {type_of_cost}.'
            )
        popup.open()

    def _next_screen(self):
        if not self.manager.has_screen('save_results_techs'):
            screen = TechSelectionSaveResults(name='save_results_techs')
            self.manager.add_widget(screen)

        self.manager.transition.duration = BASE_TRANSITION_DUR
        self.manager.transition.direction = 'left'
        self.manager.current = 'save_results_techs'


class TechSelectionSaveResults(Screen):
    """"""
    def __init__(self, **kwargs):
        super(TechSelectionSaveResults, self).__init__(**kwargs)
        # self.sm = sm

    def feasibility_export_png(self):
        """Exports currently displayed figure to .png file in specified location."""
        filename = self.name_plot_feasibility.text
        if filename == '':
            filename = 'out_plot_feasibility'
        outname = os.path.join('results', 'tech_selection', f'{filename}.png')
        self.manager.get_screen('feasible_techs').plot_feasibility.children[0].export_to_png(outname)

        popup = WarningPopup(size_hint=(0.4, 0.4))
        popup.title = 'Success!'
        popup.popup_text.text = f'Figure successfully exported to:\n\n {os.path.abspath(outname)}'
        popup.open()

    def ranking_export_png(self):
        """Exports currently displayed figure to .png file in specified location."""
        filename = self.name_plot_ranking.text
        if filename == '':
            filename = 'out_plot_ranking'
        outname = os.path.join('results', 'tech_selection', f'{filename}.png')
        self.manager.get_screen('ranking_techs').plot_ranking.children[0].export_to_png(outname)

        popup = WarningPopup(size_hint=(0.4, 0.4))
        popup.title = 'Success!'
        popup.popup_text.text = f'Figure successfully exported to:\n\n {os.path.abspath(outname)}'
        popup.open()

    def ranking_export_csv(self):
        """Exports ranking DataFrame to .csv file in specified location."""
        filename = self.name_table_ranking.text
        if filename == '':
            filename = 'out_table_ranking'
        outname = os.path.join('results', 'tech_selection', f'{filename}.csv')
        self.manager.get_screen('ranking_techs').dfRanking.to_csv(outname)

        popup = WarningPopup(size_hint=(0.4, 0.4))
        popup.title = 'Success!'
        popup.popup_text.text = 'Results file successfully exported to:\n\n' + os.path.abspath(outname)
        popup.open()