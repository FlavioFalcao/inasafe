import numpy
from safe.common.utilities import OrderedDict
from safe.defaults import get_defaults
from safe.impact_functions.core import (
    FunctionProvider,
    get_hazard_layer,
    get_exposure_layer,
    get_question,
    get_function_title,
    default_minimum_needs,
    evacuated_population_weekly_needs)
from safe.storage.raster import Raster
from safe.common.utilities import (
    ugettext as tr,
    format_int,
    verify,
    round_thousand,
    humanize_class,
    create_classes,
    create_label,
    get_thousand_separator)
from safe.common.tables import Table, TableRow
from safe.common.exceptions import ZeroImpactException
from safe.keywords.keywords_management import ImpactKeywords
from safe.keywords.table_formatter import TableFormatter


class FloodEvacuationFunction(FunctionProvider):
    """Impact function for flood evacuation

    :author AIFDR
    :rating 4
    :param requires category=='hazard' and \
                    subcategory in ['flood', 'tsunami'] and \
                    layertype=='raster' and \
                    unit=='m'

    :param requires category=='exposure' and \
                    subcategory=='population' and \
                    layertype=='raster'
    """

    title = tr('Need evacuation')
    function_id = 'FloodEvacuationFunction'
    defaults = get_defaults()

    # Function documentation
    synopsis = tr(
        'To assess the impacts of (flood or tsunami) inundation in raster '
        'format on population.')
    actions = tr(
        'Provide details about how many people would likely need to be '
        'evacuated, where they are located and what resources would be '
        'required to support them.')
    detailed_description = tr(
        'The population subject to inundation exceeding a threshold '
        '(default 1m) is calculated and returned as a raster layer. In '
        'addition the total number and the required needs in terms of the '
        'BNPB (Perka 7) are reported. The threshold can be changed and even '
        'contain multiple numbers in which case evacuation and needs are '
        'calculated using the largest number with population breakdowns '
        'provided for the smaller numbers. The population raster is resampled '
        'to the resolution of the hazard raster and is rescaled so that the '
        'resampled population counts reflect estimates of population count '
        'per resampled cell. The resulting impact layer has the same '
        'resolution and reflects population count per cell which are affected '
        'by inundation.')
    hazard_input = tr(
        'A hazard raster layer where each cell represents flood depth '
        '(in meters).')
    exposure_input = tr(
        'An exposure raster layer where each cell represent population count.')
    output = tr(
        'Raster layer contains population affected and the minimum needs '
        'based on the population affected.')
    limitation = tr(
        'The default threshold of 1 meter was selected based on consensus, '
        'not hard evidence.')

    # Configurable parameters
    # TODO: Share the mimimum needs and make another default value
    parameters = OrderedDict([
        ('thresholds [m]', [1.0]),
        ('postprocessors', OrderedDict([
            ('Gender', {'on': True}),
            ('Age', {
                'on': True,
                'params': OrderedDict([
                    ('youth_ratio', defaults['YOUTH_RATIO']),
                    ('adult_ratio', defaults['ADULT_RATIO']),
                    ('elder_ratio', defaults['ELDER_RATIO'])])}),
            ('MinimumNeeds', {'on': True}),
        ])),
        ('minimum needs', default_minimum_needs())
    ])

    def run(self, layers):
        """Risk plugin for flood population evacuation

        Input
          layers: List of layers expected to contain
              my_hazard: Raster layer of flood depth
              my_exposure: Raster layer of population data on the same grid
              as my_hazard

        Counts number of people exposed to flood levels exceeding
        specified threshold.

        Return
          Map of population exposed to flood levels exceeding the threshold
          Table with number of people evacuated and supplies required
        """

        impact_keywords = ImpactKeywords()
        impact_keywords.primary_layer.set_function_details(self)
        impact_keywords.primary_layer.set_title(
            tr('People in need of evacuation'))

        # Identify hazard and exposure layers
        my_hazard = get_hazard_layer(layers)  # Flood inundation [m]
        my_exposure = get_exposure_layer(layers)
        impact_keywords.set_provenance_layer(my_hazard, 'impact_layer')
        impact_keywords.set_provenance_layer(my_exposure, 'exposure_layer')

        # Determine depths above which people are regarded affected [m]
        # Use thresholds from inundation layer if specified
        thresholds = self.parameters['thresholds [m]']

        verify(isinstance(thresholds, list),
               'Expected thresholds to be a list. Got %s' % str(thresholds))

        # Extract data as numeric arrays
        D = my_hazard.get_data(nan=0.0)  # Depth

        # Calculate impact as population exposed to depths > max threshold
        P = my_exposure.get_data(nan=0.0, scaling=True)

        # Calculate impact to intermediate thresholds
        counts = []
        # merely initialize
        my_impact = None
        for i, lo in enumerate(thresholds):
            if i == len(thresholds) - 1:
                # The last threshold
                my_impact = M = numpy.where(D >= lo, P, 0)
            else:
                # Intermediate thresholds
                hi = thresholds[i + 1]
                M = numpy.where((D >= lo) * (D < hi), P, 0)

            # Count
            val = int(numpy.sum(M))

            # Don't show digits less than a 1000
            val = round_thousand(val)
            counts.append(val)

        # Count totals
        evacuated = counts[-1]
        total = int(numpy.sum(P))
        # Don't show digits less than a 1000
        total = round_thousand(total)

        # Calculate estimated minimum needs
        # The default value of each logistic is based on BNPB Perka 7/2008
        # minimum bantuan
        minimum_needs = self.parameters['minimum needs']
        tot_needs = evacuated_population_weekly_needs(
            evacuated, minimum_needs, detailed=True)

        impact_keywords.primary_layer.set_minimum_needs(tot_needs)
        impact_keywords.primary_layer.set_impact_assesment_population(
            'flood', evacuated, evacuated, total,
            dict(zip(thresholds, counts)))

        # Create the table here. The keywords object will be passed on,
        # but let us make the loop small for now...
        tf = TableFormatter(impact_keywords)
        impact_summary = tf().toNewlineFreeString()
        impact_table = impact_summary

        # check for zero impact
        if numpy.nanmax(my_impact) == 0 == numpy.nanmin(my_impact):
            question = get_question(
                my_hazard.get_name(), my_exposure.get_name(), self)
            table_body = [
                question,
                TableRow([(tr('People in %.1f m of water') % thresholds[-1]),
                          '%s' % format_int(evacuated)],
                         header=True)]
            my_message = Table(table_body).toNewlineFreeString()
            raise ZeroImpactException(my_message)

        # Create style
        colours = ['#FFFFFF', '#38A800', '#79C900', '#CEED00',
                   '#FFCC00', '#FF6600', '#FF0000', '#7A0000']
        classes = create_classes(my_impact.flat[:], len(colours))
        interval_classes = humanize_class(classes)
        style_classes = []

        for i in xrange(len(colours)):
            style_class = dict()
            if i == 1:
                label = create_label(interval_classes[i], 'Low')
            elif i == 4:
                label = create_label(interval_classes[i], 'Medium')
            elif i == 7:
                label = create_label(interval_classes[i], 'High')
            else:
                label = create_label(interval_classes[i])
            style_class['label'] = label
            style_class['quantity'] = classes[i]
            if i == 0:
                transparency = 100
            else:
                transparency = 0
            style_class['transparency'] = transparency
            style_class['colour'] = colours[i]
            style_classes.append(style_class)

        style_info = dict(target_field=None,
                          style_classes=style_classes,
                          style_type='rasterStyle')

        # For printing map purpose
        map_title = tr('People in need of evacuation')
        legend_notes = tr('Thousand separator is represented by %s' %
                          get_thousand_separator())
        legend_units = tr('(people per cell)')
        legend_title = tr('Population density')

        # Create raster object and return
        R = Raster(my_impact,
                   projection=my_hazard.get_projection(),
                   geotransform=my_hazard.get_geotransform(),
                   name=tr('Population which %s') % (
                       get_function_title(self).lower()),
                   # This will take the keywords object next
                   # keywords={'impact_summary': impact_summary,
                   #           'impact_table': impact_table,
                   #           'map_title': map_title,
                   #           'legend_notes': legend_notes,
                   #           'legend_units': legend_units,
                   #           'legend_title': legend_title,
                   #           'evacuated': evacuated,
                   #           'total_needs': tot_needs},
                   keywords={'json': impact_keywords, 'html': impact_table},
                   style_info=style_info)
        return R
