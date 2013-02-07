import numpy
from safe.impact_functions.core import (FunctionProvider,
                                        get_hazard_layer,
                                        get_exposure_layer,
                                        get_question,
                                        format_int)
from safe.storage.vector import Vector
from safe.common.utilities import ugettext as tr
from safe.common.tables import Table, TableRow
from safe.engine.interpolation import assign_hazard_values_to_exposure_data
from safe.common.utilities import get_defaults
from third_party.odict import OrderedDict


class FloodEvacuationFunctionVectorHazard(FunctionProvider):
    """Impact function for flood evacuation

    :author AIFDR
    :rating 4
    :param requires category=='hazard' and \
                    subcategory in ['flood', 'tsunami'] and \
                    layertype=='vector'

    :param requires category=='exposure' and \
                    subcategory=='population' and \
                    layertype=='raster'
    """

    title = tr('Need evacuation')
    target_field = 'population'
    defaults = get_defaults()
    parameters = OrderedDict([
        ('evacuation_percentage', 1),  # Percent of affected needing evac
        ('postprocessors', OrderedDict([
            ('Gender', {'on': True}),
            ('Age', {
                'on': True,
                'params': OrderedDict([
                    ('youth_ratio', defaults['YOUTH_RATIO']),
                    ('adult_ratio', defaults['ADULT_RATIO']),
                    ('elder_ratio', defaults['ELDER_RATIO'])])})]))])

    def run(self, layers):
        """Risk plugin for flood population evacuation

        Input
          layers: List of layers expected to contain
              H: Vector polygon layer of flood depth
              P: Raster layer of population data on the same grid as H

        Counts number of people exposed to areas identified as flood prone

        Return
          Map of population exposed to flooding
          Table with number of people evacuated and supplies required
        """
        # Identify hazard and exposure layers
        H = get_hazard_layer(layers)  # Flood inundation
        E = get_exposure_layer(layers)

        question = get_question(H.get_name(),
                                E.get_name(),
                                self)

        # Check that hazard is polygon type
        if not H.is_vector:
            msg = ('Input hazard %s  was not a vector layer as expected '
                   % H.get_name())
            raise Exception(msg)

        msg = ('Input hazard must be a polygon layer. I got %s with layer '
               'type %s' % (H.get_name(),
                            H.get_geometry_name()))
        if not H.is_polygon_data:
            raise Exception(msg)

        # Run interpolation function for polygon2raster
        P = assign_hazard_values_to_exposure_data(H, E,
                                             attribute_name='population')

        # Initialise attributes of output dataset with all attributes
        # from input polygon and a population count of zero
        new_attributes = H.get_data()
        category_title = 'FLOODPRONE'  # FIXME: Should come from keywords
        categories = {}
        for attr in new_attributes:
            attr[self.target_field] = 0
            cat = attr[category_title]
            categories[cat] = 0

        # Count affected population per polygon, per category and total
        affected_population = 0
        for attr in P.get_data():

            affected = False
            if 'affected' in attr:
                res = attr['affected']
                if res is not None:
                    affected = res
            elif 'FLOODPRONE' in attr:
                # If there isn't an 'affected' attribute,
                res = attr['FLOODPRONE']
                if res is not None:
                    affected = res.lower() == 'yes'
            elif 'Affected' in attr:
                # Check the default attribute assigned for points
                # covered by a polygon
                res = attr['Affected']
                if res is None:
                    x = False
                else:
                    x = res
            else:
                # there is no flood related attribute
                msg = ('No flood related attribute found in %s. '
                       'I was looking fore either "Flooded", "FLOODPRONE" '
                       'or "Affected". The latter should have been '
                       'automatically set by call to '
                       'assign_hazard_values_to_exposure_data(). '
                       'Sorry I can\'t help more.')
                raise Exception(msg)

            if affected:
                # Get population at this location
                pop = float(attr['population'])

                # Update population count for associated polygon
                poly_id = attr['polygon_id']
                new_attributes[poly_id][self.target_field] += pop

                # Update population count for each category
                cat = new_attributes[poly_id][category_title]
                categories[cat] += pop

                # Update total
                affected_population += pop

        # Estimate number of people in need of evacuation
        evacuated = (affected_population *
                     self.parameters['evacuation_percentage']
                     / 100.0)

        total = int(numpy.sum(E.get_data(nan=0, scaling=False)))

        # Don't show digits less than a 1000
        if total > 1000:
            total = total // 1000 * 1000
        if evacuated > 1000:
            evacuated = evacuated // 1000 * 1000

        # Calculate estimated needs based on BNPB Perka 7/2008 minimum bantuan
        rice = evacuated * 2.8  # 400g per person per day
        drinking_water = evacuated * 17.5  # 2.5L per person per day
        water = evacuated * 105  # 15L per person per day
        family_kits = evacuated / 5  # assume 5 people per family
        toilets = evacuated / 20  # 20 people to 1 toilet

        # Generate impact report for the pdf map
        table_body = [question,
                      TableRow([tr('People needing evacuation'),
                                '%s' % format_int(evacuated)],
                               header=True),
                      TableRow(tr('Map shows population affected in each flood'
                                 ' prone area ')),
                      TableRow([tr('Needs per week'), tr('Total')],
                               header=True),
                      [tr('Rice [kg]'), format_int(int(rice))],
                      [tr('Drinking Water [l]'),
                            format_int(int(drinking_water))],
                      [tr('Clean Water [l]'), format_int(int(water))],
                      [tr('Family Kits'), format_int(int(family_kits))],
                      [tr('Toilets'), format_int(int(toilets))]]
        impact_table = Table(table_body).toNewlineFreeString()

        table_body.append(TableRow(tr('Action Checklist:'), header=True))
        table_body.append(TableRow(tr('How will warnings be disseminated?')))
        table_body.append(TableRow(tr('How will we reach stranded people?')))
        table_body.append(TableRow(tr('Do we have enough relief items?')))
        table_body.append(TableRow(tr('If yes, where are they located and how '
                                     'will we distribute them?')))
        table_body.append(TableRow(tr('If no, where can we obtain additional '
                                     'relief items from and how will we '
                                     'transport them to here?')))

        # Extend impact report for on-screen display
        table_body.extend([TableRow(tr('Notes'), header=True),
                           tr('Total population: %s') % format_int(total),
                           tr('People need evacuation if in area identified '
                             'as "Flood Prone"'),
                           tr('Minimum needs are defined in BNPB '
                             'regulation 7/2008')])
        impact_summary = Table(table_body).toNewlineFreeString()
        map_title = tr('People affected by flood prone areas')

        # Define classes for legend for flooded population counts
        colours = ['#FFFFFF', '#38A800', '#79C900', '#CEED00',
                   '#FFCC00', '#FF6600', '#FF0000', '#7A0000']
        population_counts = [x['population'] for x in new_attributes]
        cls = [0] + numpy.linspace(1,
                                   max(population_counts),
                                   len(colours)).tolist()

        # Define style info for output polygons showing population counts
        style_classes = []
        for i, colour in enumerate(colours):
            lo = cls[i]
            hi = cls[i + 1]

            if i == 0:
                label = tr('0')
                transparency = 100
            else:
                label = tr('%i - %i') % (lo, hi)
                transparency = 0

            entry = dict(label=label, colour=colour, min=lo, max=hi,
                         transparency=transparency, size=1)
            style_classes.append(entry)

        # Override style info with new classes and name
        style_info = dict(target_field=self.target_field,
                          style_classes=style_classes,
                          legend_title=tr('Population Count'))

        # Create vector layer and return
        V = Vector(data=new_attributes,
                   projection=H.get_projection(),
                   geometry=H.get_geometry(),
                   name=tr('Population affected by flood prone areas'),
                   keywords={'impact_summary': impact_summary,
                             'impact_table': impact_table,
                             'map_title': map_title,
                             'target_field': self.target_field},
                   style_info=style_info)
        return V
