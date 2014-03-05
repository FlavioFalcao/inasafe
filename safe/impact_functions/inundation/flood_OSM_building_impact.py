from safe.common.utilities import OrderedDict

from safe.impact_functions.core import (
    FunctionProvider, get_hazard_layer, get_exposure_layer)
from safe.storage.vector import Vector
from safe.storage.utilities import DEFAULT_ATTRIBUTE
from safe.common.utilities import (ugettext as tr, verify)
from safe.engine.interpolation import assign_hazard_values_to_exposure_data
from safe.keywords.keywords_management import ImpactKeywords
from safe.keywords.table_formatter import TableFormatter

import logging
LOGGER = logging.getLogger('InaSAFE')


class FloodBuildingImpactFunction(FunctionProvider):
    """Inundation impact on building data

    :author Ole Nielsen, Kristy van Putten
    # this rating below is only for testing a function, not the real one
    :rating 0
    :param requires category=='hazard' and \
                    subcategory in ['flood', 'tsunami']

    :param requires category=='exposure' and \
                    subcategory=='structure' and \
                    layertype=='vector'
    """

    # Function documentation
    target_field = 'INUNDATED'
    title = tr('Be flooded')
    function_id = 'Flood Building Impact Function'
    synopsis = tr(
        'To assess the impacts of (flood or tsunami) inundation on building '
        'footprints originating from OpenStreetMap (OSM).')
    actions = tr(
        'Provide details about where critical infrastructure might be flooded')
    detailed_description = tr(
        'The inundation status is calculated for each building (using the '
        'centroid if it is a polygon) based on the hazard levels provided. if '
        'the hazard is given as a raster a threshold of 1 meter is used. This '
        'is configurable through the InaSAFE interface. If the hazard is '
        'given as a vector polygon layer buildings are considered to be '
        'impacted depending on the value of hazard attributes (in order) '
        '"affected" or "FLOODPRONE": If a building is in a region that has '
        'attribute "affected" set to True (or 1) it is impacted. If attribute '
        '"affected" does not exist but "FLOODPRONE" does, then the building '
        'is considered impacted if "FLOODPRONE" is "yes". If neither '
        '"affected" nor "FLOODPRONE" is available, a building will be '
        'impacted if it belongs to any polygon. The latter behaviour is '
        'implemented through the attribute "inapolygon" which is automatically'
        ' assigned.')
    hazard_input = tr(
        'A hazard raster layer where each cell represents flood depth (in '
        'meters), or a vector polygon layer where each polygon represents an '
        'inundated area. In the latter case, the following attributes are '
        'recognised (in order): "affected" (True or False) or "FLOODPRONE" '
        '(Yes or No). (True may be represented as 1, False as 0')
    exposure_input = tr(
        'Vector polygon layer extracted from OSM where each polygon '
        'represents the footprint of a building.')
    output = tr(
        'Vector layer contains building is estimated to be flooded and the '
        'breakdown of the building by type.')
    limitation = tr(
        'This function only flags buildings as impacted or not either based '
        'on a fixed threshold in case of raster hazard or the the attributes '
        'mentioned under input in case of vector hazard.')

    # parameters
    parameters = OrderedDict([
        ('threshold [m]', 1.0),
        ('postprocessors', OrderedDict([('BuildingType', {'on': True})]))])

    def run(self, layers):
        """Flood impact to buildings (e.g. from Open Street Map).

        :param layers: The layers to be used in this impact function analysis.
        :type layers: itterable

        :returns: An impact layer.
        :rtype: Vector
        """

        impact_keywords = ImpactKeywords()
        impact_keywords.set_function_details(self)
        impact_keywords.set_title(tr('Estimated buildings affected'))

        threshold = self.parameters['threshold [m]']  # Flood threshold [m]

        verify(isinstance(threshold, float),
               'Expected thresholds to be a float. Got %s' % str(threshold))

        # Extract data
        H = get_hazard_layer(layers)    # Depth
        E = get_exposure_layer(layers)  # Building locations
        impact_keywords.set_provenance_layer(H, 'impact_layer')
        impact_keywords.set_provenance_layer(E, 'exposure_layer')

        # Determine attribute name for hazard levels
        if H.is_raster:
            mode = 'grid'
            hazard_attribute = 'depth'
        else:
            mode = 'regions'
            hazard_attribute = None

        # Interpolate hazard level to building locations
        I = assign_hazard_values_to_exposure_data(
            H, E, attribute_name=hazard_attribute)

        # Extract relevant exposure data
        attribute_names = I.get_attribute_names()
        attributes = I.get_data()
        N = len(I)
        # Calculate building impact
        count = 0
        buildings = {}
        affected_buildings = {}
        for i in range(N):
            if mode == 'grid':
                # Get the interpolated depth
                x = float(attributes[i]['depth'])
                x = x >= threshold
            elif mode == 'regions':
                # Use interpolated polygon attribute
                atts = attributes[i]

                # FIXME (Ole): Need to agree whether to use one or the
                # other as this can be very confusing!
                # For now look for 'affected' first
                if 'affected' in atts:
                    # E.g. from flood forecast
                    # Assume that building is wet if inside polygon
                    # as flagged by attribute Flooded
                    res = atts['affected']
                    if res is None:
                        x = False
                    else:
                        x = bool(res)

                elif 'FLOODPRONE' in atts:
                    res = atts['FLOODPRONE']
                    if res is None:
                        x = False
                    else:
                        x = res.lower() == 'yes'
                elif DEFAULT_ATTRIBUTE in atts:
                    # Check the default attribute assigned for points
                    # covered by a polygon
                    res = atts[DEFAULT_ATTRIBUTE]
                    if res is None:
                        x = False
                    else:
                        x = res
                else:
                    # there is no flood related attribute
                    msg = ('No flood related attribute found in %s. '
                           'I was looking for either "affected", "FLOODPRONE" '
                           'or "inapolygon". The latter should have been '
                           'automatically set by call to '
                           'assign_hazard_values_to_exposure_data(). '
                           'Sorry I can\'t help more.')
                    raise Exception(msg)
            else:
                msg = (tr(
                    'Unknown hazard type %s. Must be either "depth" or "grid"')
                    % mode)
                raise Exception(msg)

            # Count affected buildings by usage type if available
            if 'type' in attribute_names:
                usage = attributes[i]['type']
            elif 'TYPE' in attribute_names:
                usage = attributes[i]['TYPE']
            else:
                usage = None
            if 'amenity' in attribute_names and (usage is None or usage == 0):
                usage = attributes[i]['amenity']
            if 'building_t' in attribute_names and (usage is None
                                                    or usage == 0):
                usage = attributes[i]['building_t']
            if 'office' in attribute_names and (usage is None or usage == 0):
                usage = attributes[i]['office']
            if 'tourism' in attribute_names and (usage is None or usage == 0):
                usage = attributes[i]['tourism']
            if 'leisure' in attribute_names and (usage is None or usage == 0):
                usage = attributes[i]['leisure']
            if 'building' in attribute_names and (usage is None or usage == 0):
                usage = attributes[i]['building']
                if usage == 'yes':
                    usage = 'building'

            if usage is not None and usage != 0:
                key = usage
            else:
                key = 'unknown'

            if key not in buildings:
                buildings[key] = 0
                affected_buildings[key] = 0

            # Count all buildings by type
            buildings[key] += 1
            if x is True:
                # Count affected buildings by type
                affected_buildings[key] += 1

                # Count total affected buildings
                count += 1

            # Add calculated impact to existing attributes
            attributes[i][self.target_field] = int(x)

        # Lump small entries and 'unknown' into 'other' category
        for usage in buildings.keys():
            x = buildings[usage]
            if usage == 'unknown':
                if 'other' not in buildings:
                    buildings['other'] = 0
                    affected_buildings['other'] = 0

                buildings['other'] += x
                affected_buildings['other'] += affected_buildings[usage]
                del buildings[usage]
                del affected_buildings[usage]

        impact_keywords.primary_layer.set_buildings_breakdown(
            buildings, {'affected_buildings': affected_buildings})
        impact_keywords.primary_layer.set_impact_assessment_buildings(
            'buildings', 'flood', buildings,
            {'affected': affected_buildings})

        # Create the table here. The keywords object will be passed on,
        # but let us make the loop small for now...
        tf = TableFormatter(impact_keywords)
        impact_summary = tf().toNewlineFreeString()
        impact_table = impact_summary

        # Create style
        style_classes = [dict(label=tr('Not Inundated'), value=0,
                              colour='#1EFC7C', transparency=0, size=1),
                         dict(label=tr('Inundated'), value=1,
                              colour='#F31A1C', transparency=0, size=1)]
        style_info = dict(target_field=self.target_field,
                          style_classes=style_classes,
                          style_type='categorizedSymbol')

        # For printing map purpose
        map_title = tr('Buildings inundated')
        legend_units = tr('(inundated or not inundated)')
        legend_title = tr('Structure inundated status')

        # Create vector layer and return
        V = Vector(data=attributes,
                   projection=I.get_projection(),
                   geometry=I.get_geometry(),
                   name=tr('Estimated buildings affected'),
                   # This will take the keywords object next
                   keywords={'impact_summary': impact_summary,
                             'impact_table': impact_table,
                             'target_field': self.target_field,
                             'map_title': map_title,
                             'legend_units': legend_units,
                             'legend_title': legend_title},
                   style_info=style_info)
        return V
