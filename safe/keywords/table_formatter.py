# -*- coding: utf-8 -*-
"""**Handle JSON keywords file.**

Classes to handle the creation and ingestion of keywords data in JASON format.
"""
__author__ = 'cchristelis@gmail.com'
__version__ = '0.1'
__date__ = '10/11/2013'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')

from safe.impact_functions.core import get_question
from safe.common.tables import Table, TableRow, TableCell
from safe.common.utilities import ugettext as tr, format_int


class TableFormatter(object):
    """Format a keywords object into a table.

    :param keywords: A keywords instance.
    """

    def __init__(self, keywords):
        self.keywords = keywords

    def __call__(self, table_type='Analysis Result'):
        """Call the Table Formatter as a function.

        :param table_type: The type of table we wish to obtain. (
            Currently only the default 'Analysis Result' is used)
        :type table_type: str

        :return: A table of teh desired type based on the initialized keywords.
        :rtype: Table
        """
        if table_type == 'Analysis Result':
            return self.analysis_table()
        elif table_type == 'Complete Analysis Result':
            return self.analysis_table_complete()

    def _table_body(self):
        """Get the tabulated form of the impact breakdown

        :return: Impact breakdown table.
        :rtype: list
        """
        def _format(item):
            if type(item) == int:
                return format_int(item)
            return item

        breakdown = self.keywords.primary_layer.impact_breakdown
        heading = [breakdown.category_label or ''] + breakdown.get_attributes()
        table = [TableRow(heading, header=True)]
        for category in breakdown.get_categories():
            row = [category]
            for attribute in breakdown.get_attributes():
                row.append(_format(breakdown[category, attribute]))
            table.append(row)
        return table

    @staticmethod
    def _get_reduced_totals(buildings_affected, min_group_count=25):
        buildings_reduced = {}
        for building_type in buildings_affected:
            building_type_data = buildings_affected[building_type]
            if building_type_data["affected"] < min_group_count:
                if 'other' not in buildings_reduced:
                    buildings_reduced['other'] = {
                        'total': building_type_data['total'],
                        'affected': building_type_data['affected']}
                else:
                    buildings_reduced['other'][
                        'total'] += building_type_data['total']
                    buildings_reduced['other'][
                        'affected'] += building_type_data['affected']
            else:
                buildings_reduced[building_type] = buildings_affected[
                    building_type]

        return buildings_reduced

    @staticmethod
    def _add_population_needs_table(total_needs):
            table = []
            table.append(TableRow(
                [tr('Needs per week'), tr('Total')], header=True))
            food = total_needs['food']
            drinking_water = total_needs['drinking_water']
            clean_water = total_needs['clean_water']
            hygine_pack = total_needs['hygine_pack']
            toilet = total_needs['toilet']
            for resource in [
                    food, drinking_water, clean_water]:
                table.append([
                    tr('%s [%s]' % (
                        resource['type'], resource['unit_abbreviation'])),
                    format_int(resource['quantity'])])
            for resource in [hygine_pack, toilet]:
                table.append([
                    tr('%s' % resource['type']),
                    format_int(resource['quantity'])])
            return table

    @staticmethod
    def _add_action_checklist(table_body, impact, hazard):
        if hazard == 'population' and impact == 'inundation':
            table_body.append(TableRow(tr('Action Checklist:'), header=True))
            table_body.append(TableRow(
                tr('How will warnings be disseminated?')))
            table_body.append(TableRow(
                tr('How will we reach stranded people?')))
            table_body.append(TableRow(tr('Do we have enough relief items?')))
            table_body.append(TableRow(tr(
                'If yes, where are they located and how will we distribute '
                'them?')))
            table_body.append(TableRow(tr(
                'If no, where can we obtain additional relief items from and '
                'how will we transport them to here?')))


    @staticmethod
    def _format_thousands(name, value, header=False):
        return TableRow([tr(name), '%s%s' % (
            format_int(int(value)),
            ('*' if value >= 1000 else ''))], header=header)


class BuildingTable(TableFormatter):
    def analysis_table(self):

        table = [get_question(
            self.keywords.provenance['impact_layer']['name'],
            self.keywords.provenance['exposure_layer']['name'],
            self.keywords.primary_layer.function_details['title'])]
        table += self._table_body()
        table += self._get_action_checklist()
        return Table(table)

    def _get_action_checklist(self):
        parameters = self.keywords.function_details['parameters']
        t0 = parameters['low_threshold']
        t1 = parameters['medium_threshold']
        t2 = parameters['high_threshold']
        table = [
            tr('High hazard is defined as shake levels greater '
                'than %i on the MMI scale.') % t2,
            tr('Medium hazard is defined as shake levels '
                'between %i and %i on the MMI scale.') % (t1, t2),
            tr('Low hazard is defined as shake levels '
                'between %i and %i on the MMI scale.') % (t0, t1)]
        return table


class PopulationEarthquakeTable(TableFormatter):
    def analysis_table(self):
        table = [get_question(
            self.keywords.provenance['impact_layer']['name'],
            self.keywords.provenance['exposure_layer']['name'],
            self.keywords.primary_layer.function_details['title'])]
        table += self._table_body()
        table += [tr('Map shows density estimate of displaced population')]
        minimum_needs = self.keywords.primary_layer.minimum_needs
        table += self._add_population_needs_table(minimum_needs)
        table += self._get_action_checklist()
        table += self._get_notes()
        return Table(table)

    def _get_action_checklist(self):
        breakdown = self.keywords.primary_layer.impact_breakdown
        fatalities = breakdown[tr('Fatalities'), tr('population')]
        displaced = breakdown[tr('People displaced'), tr('population')]

        table = [TableRow(tr('Action Checklist:'), header=True)]
        if fatalities:
            table.append(
                tr('Are there enough victim identification units available '
                   'for %s people?') % format_int(fatalities))
        if displaced:
            table.append(
                tr('Are there enough shelters and relief items available for '
                   '%s people?') % format_int(displaced))
            table.append(TableRow(
                tr('If yes, where are they located and how will we distribute '
                   'them?')))
            table.append(TableRow(
                tr('If no, where can we obtain additional relief items from '
                   'and how will we transport them?')))
        return table

    def _get_notes(self):
        breakdown = self.keywords.primary_layer.impact_breakdown
        total = breakdown[tr('Total population'), tr('population')]
        return [
            TableRow(tr('Notes'), header=True),
            tr('Total population: %s') % format_int(total),
            tr('People are considered to be displaced if they experience and '
               'survive a shake level of more than 5 on the MMI scale '),
            tr('Minimum needs are defined in BNPB regulation 7/2008'),
            tr('The fatality calculation assumes that no fatalities occur for '
               'shake levels below 4 and fatality counts of less than 50 are '
                'disregarded.'),
            tr('All values are rounded up to the nearest integer in order to '
               'avoid representing human lives as fractions.'),
            TableRow(tr('Notes'), header=True),
            tr('Fatality model is from Institute of Teknologi Bandung 2012.'),
            tr('Population numbers rounded to nearest 1000.')]



def TableSelector(keywords):
    if keywords.impact_assessment['exposure_subcategory'] == 'buildings':
        return BuildingTable(keywords)
    if keywords.impact_assessment['exposure_subcategory'] == 'population':
        if keywords.impact_assessment['hazard_subcategory'] == 'earthquake':
            return PopulationEarthquakeTable(keywords)
