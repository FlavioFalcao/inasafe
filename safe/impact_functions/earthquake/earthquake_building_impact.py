# coding=utf-8
"""Earthquake Impact Function on Building."""

from safe.common.utilities import OrderedDict
from safe.impact_functions.core import (
    FunctionProvider, get_hazard_layer, get_exposure_layer, get_question)
from safe.storage.vector import Vector
from safe.common.utilities import (ugettext as tr, format_int)
from safe.engine.interpolation import assign_hazard_values_to_exposure_data
from safe.keywords.keywords_management import ImpactKeywords, ImpactBreakdown
from safe.keywords.table_formatter import TableSelector

import logging

LOGGER = logging.getLogger('InaSAFE')


class EarthquakeBuildingImpactFunction(FunctionProvider):
    """Earthquake impact on building data

    :param requires category=='hazard' and \
                    subcategory=='earthquake'

    :param requires category=='exposure' and \
                    subcategory=='structure' and \
                    layertype=='vector'
    """

    target_field = 'Shake_cls'
    function_id = 'Earthquake Building Impact Function'
    synopsis = tr(
        'To assess the impacts of earthquake on buildings, based on shake '
        'levels')
    detailed_description = '',
    hazard_input = tr(
        'A hazard raster layer where each cell represents sake.')
    exposure_input = tr(
        'Vector polygon layer where each polygon '
        'represents the footprint of a building.')
    statistics_type = 'class_count'
    statistics_classes = [0, 1, 2, 3]
    title = tr('Be affected')
    parameters = OrderedDict(
        [('low_threshold', 6),
         ('medium_threshold', 7),
         ('high_threshold', 8),
         ('postprocessors', OrderedDict([
         ('AggregationCategorical', {'on': True})]))
         ])

    def run(self, layers):
        """Earthquake impact to buildings (e.g. from OpenStreetMap)
        :param layers: All the input layers (Hazard Layer and Exposure Layer)
        """

        impact_keywords = ImpactKeywords()
        impact_keywords.set_function_details(self)
        impact_keywords.set_title(tr('Estimated buildings affected'))

        LOGGER.debug('Running earthquake building impact')

        # merely initialize
        building_value = 0
        contents_value = 0

        # Thresholds for mmi breakdown
        t0 = self.parameters['low_threshold']
        t1 = self.parameters['medium_threshold']
        t2 = self.parameters['high_threshold']

        # Class Attribute and Label

        class_1 = {'label': tr('Low'), 'class': 1}
        class_2 = {'label': tr('Medium'), 'class': 2}
        class_3 = {'label': tr('High'), 'class': 3}

        # Extract data
        my_hazard = get_hazard_layer(layers)    # Depth
        my_exposure = get_exposure_layer(layers)  # Building locations
        impact_keywords.set_provenance_layer(my_hazard, 'impact_layer')
        impact_keywords.set_provenance_layer(my_exposure, 'exposure_layer')
        impact_keywords.set_impact_assesment('buildings', 'earthquake')

        question = get_question(my_hazard.get_name(),
                                my_exposure.get_name(),
                                self)

        # Define attribute name for hazard levels
        hazard_attribute = 'mmi'

        # Determine if exposure data have NEXIS attributes
        attribute_names = my_exposure.get_attribute_names()
        if ('FLOOR_AREA' in attribute_names and
            'BUILDING_C' in attribute_names and
                'CONTENTS_C' in attribute_names):
            is_nexis = True
        else:
            is_nexis = False

        # Interpolate hazard level to building locations
        my_interpolate_result = assign_hazard_values_to_exposure_data(
            my_hazard, my_exposure, attribute_name=hazard_attribute)

        # Extract relevant exposure data
        #attribute_names = my_interpolate_result.get_attribute_names()
        attributes = my_interpolate_result.get_data()

        interpolate_size = len(my_interpolate_result)

        # Calculate building impact
        unaffected = 0
        lo = 0
        me = 0
        hi = 0
        building_values = {}
        contents_values = {}
        for key in range(4):
            building_values[key] = 0
            contents_values[key] = 0
        for i in range(interpolate_size):
            # Classify building according to shake level
            # and calculate dollar losses

            if is_nexis:
                try:
                    area = float(attributes[i]['FLOOR_AREA'])
                except (ValueError, KeyError):
                    area = 0.0

                try:
                    building_value_density = float(attributes[i]['BUILDING_C'])
                except (ValueError, KeyError):
                    building_value_density = 0.0

                try:
                    contents_value_density = float(attributes[i]['CONTENTS_C'])
                except (ValueError, KeyError):
                    contents_value_density = 0.0

                building_value = building_value_density * area
                contents_value = contents_value_density * area

            try:
                x = float(attributes[i][hazard_attribute])  # MMI
            except TypeError:
                x = 0.0
            if t0 <= x < t1:
                lo += 1
                cls = 1
            elif t1 <= x < t2:
                me += 1
                cls = 2
            elif t2 <= x:
                hi += 1
                cls = 3
            else:
                unaffected += 1
                cls = 0

            attributes[i][self.target_field] = cls

            if is_nexis:
                # Accumulate values in 1M dollar units
                building_values[cls] += building_value
                contents_values[cls] += contents_value

        if is_nexis:
            # Convert to units of one million dollars
            for key in range(4):
                building_values[key] = int(building_values[key] / 1000000)
                contents_values[key] = int(contents_values[key] / 1000000)

        categories = [
            tr('Unaffected'), class_1['label'], class_2['label'],
            class_3['label']]
        if is_nexis:
            attribute_names = [
                tr('Buildings Affected'), tr('Buildings value ($M)'),
                tr('Contents value ($M)')]
        else:
            attribute_names = [tr('Buildings Affected')]
        breakdown = ImpactBreakdown(
            categories, attribute_names, 'building_breakdown')
        breakdown[tr('Unaffected'), tr('Buildings Affected')] = unaffected
        breakdown[class_1['label'], tr('Buildings Affected')] = lo
        breakdown[class_2['label'], tr('Buildings Affected')] = me
        breakdown[class_3['label'], tr('Buildings Affected')] = hi
        if is_nexis:
            for c in categories:
                breakdown[c, tr('Buildings value ($M)')] = building_values[
                    categories.index(c)]
                breakdown[c, tr('Contents value ($M)')] = contents_values[
                    categories.index(c)]

        impact_keywords.set_impact_breakdown(breakdown)
        table_formatter = TableSelector(impact_keywords)
        # if is_nexis:
        #     # Generate simple impact report for NEXIS type buildings
        #     table_formatter = NexisBuildingTable(impact_keywords)
        #
        # else:
        #     # Generate simple impact report for unspecific buildings
        #     table_formatter = BuildingTable(impact_keywords)

        impact_summary = table_formatter().toNewlineFreeString()
        impact_table = impact_summary

        # Create style
        style_classes = [dict(label=class_1['label'], value=class_1['class'],
                              colour='#ffff00', transparency=1),
                         dict(label=class_2['label'], value=class_2['class'],
                              colour='#ffaa00', transparency=1),
                         dict(label=class_3['label'], value=class_3['class'],
                              colour='#ff0000', transparency=1)]
        style_info = dict(target_field=self.target_field,
                          style_classes=style_classes,
                          style_type='categorizedSymbol')

        # For printing map purpose
        map_title = tr('Building affected by earthquake')
        legend_notes = tr('The level of the impact is according to the '
                          'threshold the user input.')
        legend_units = tr('(mmi)')
        legend_title = tr('Impact level')

        # Create vector layer and return
        result_layer = Vector(
            data=attributes,
            projection=my_interpolate_result.get_projection(),
            geometry=my_interpolate_result.get_geometry(),
            name=tr('Estimated buildings affected'),
            keywords={
                'impact_summary': impact_summary,
                'impact_table': impact_table,
                'map_title': map_title,
                'legend_notes': legend_notes,
                'legend_units': legend_units,
                'legend_title': legend_title,
                'target_field': self.target_field,
                'statistics_type': self.statistics_type,
                'statistics_classes': self
                .statistics_classes},
            style_info=style_info)

        LOGGER.debug('Created vector layer  %s' % str(result_layer))
        return result_layer
