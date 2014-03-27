"""Impact function for ITB earth quake fatality model
"""
import numpy
import logging
from safe.common.utilities import OrderedDict
from safe.defaults import get_defaults
from safe.impact_functions.core import (
    FunctionProvider,
    get_hazard_layer,
    get_exposure_layer,
    get_question,
    default_minimum_needs,
    evacuated_population_weekly_needs)
from safe.storage.raster import Raster
from safe.common.utilities import (
    ugettext as tr,
    format_int,
    humanize_class,
    create_classes,
    create_label,
    get_thousand_separator)
from safe.common.tables import Table, TableRow
from safe.common.exceptions import InaSAFEError, ZeroImpactException
from safe.keywords.keywords_management import ImpactKeywords, ImpactBreakdown
from safe.keywords.table_formatter import TableSelector

LOGGER = logging.getLogger('InaSAFE')


class ITBFatalityFunction(FunctionProvider):
    """Indonesian Earthquake Fatality Model

    This model was developed by Institut Teknologi Bandung (ITB) and
    implemented by Dr. Hadi Ghasemi, Geoscience Australia.


    Reference:

    Indonesian Earthquake Building-Damage and Fatality Models and
    Post Disaster Survey Guidelines Development,
    Bali, 27-28 February 2012, 54pp.


    Algorithm:

    In this study, the same functional form as Allen (2009) is adopted
    to express fatality rate as a function of intensity (see Eq. 10 in the
    report). The Matlab built-in function (fminsearch) for  Nelder-Mead
    algorithm was used to estimate the model parameters. The objective
    function (L2G norm) that is minimised during the optimisation is the
    same as the one used by Jaiswal et al. (2010).

    The coefficients used in the indonesian model are
    x=0.62275231, y=8.03314466, zeta=2.15

    Allen, T. I., Wald, D. J., Earle, P. S., Marano, K. D., Hotovec, A. J.,
    Lin, K., and Hearne, M., 2009. An Atlas of ShakeMaps and population
    exposure catalog for earthquake loss modeling, Bull. Earthq. Eng. 7,
    701-718.

    Jaiswal, K., and Wald, D., 2010. An empirical model for global earthquake
    fatality estimation, Earthq. Spectra 26, 1017-1037.


    Caveats and limitations:

    The current model is the result of the above mentioned workshop and
    reflects the best available information. However, the current model
    has a number of issues listed below and is expected to evolve further
    over time.

    1 - The model is based on limited number of observed fatality
        rates during 4 past fatal events.
    2 - The model clearly over-predicts the fatality rates at
        intensities higher than VIII.
    3 - The model only estimates the expected fatality rate for a given
        intensity level; however the associated uncertainty for the proposed
        model is not addressed.
    4 - There are few known mistakes in developing the current model:
        - rounding MMI values to the nearest 0.5,
        - Implementing Finite-Fault models of candidate events, and
        - consistency between selected GMPEs with those in use by BMKG.
          These issues will be addressed by ITB team in the final report.

    Note: Because of these caveats, decisions should not be made solely on
    the information presented here and should always be verified by ground
    truthing and other reliable information sources.

    :author Hadi Ghasemi
    :rating 3

    :param requires category=='hazard' and \
                    subcategory=='earthquake' and \
                    layertype=='raster' and \
                    unit=='MMI'

    :param requires category=='exposure' and \
                    subcategory=='population' and \
                    layertype=='raster'

    """

    title = tr('Die or be displaced')
    function_id = 'ITB Fatality Function'
    synopsis = tr(
        'To assess the impact of earthquake on population based on earthquake '
        'model developed by ITB')
    citations = tr(
        ' * Indonesian Earthquake Building-Damage and Fatality Models and '
        '   Post Disaster Survey Guidelines Development Bali, 27-28 '
        '   February 2012, 54pp.\n'
        ' * Allen, T. I., Wald, D. J., Earle, P. S., Marano, K. D., '
        '   Hotovec, A. J., Lin, K., and Hearne, M., 2009. An Atlas '
        '   of ShakeMaps and population exposure catalog for '
        '   earthquake loss modeling, Bull. Earthq. Eng. 7, 701-718.\n'
        ' * Jaiswal, K., and Wald, D., 2010. An empirical model for '
        '   global earthquake fatality estimation, Earthq. Spectra '
        '   26, 1017-1037.\n')
    limitation = tr(
        ' - The model is based on limited number of observed fatality '
        '   rates during 4 past fatal events. \n'
        ' - The model clearly over-predicts the fatality rates at '
        '   intensities higher than VIII.\n'
        ' - The model only estimates the expected fatality rate '
        '   for a given intensity level; however the associated '
        '   uncertainty for the proposed model is not addressed.\n'
        ' - There are few known mistakes in developing the current '
        '   model:\n\n'
        '   * rounding MMI values to the nearest 0.5,\n'
        '   * Implementing Finite-Fault models of candidate events, and\n'
        '   * consistency between selected GMPEs with those in use by '
        '     BMKG.\n')
    actions = tr(
        'Provide details about the population will be die or displaced')
    detailed_description = tr(
        'This model was developed by Institut Teknologi Bandung (ITB) '
        'and implemented by Dr. Hadi Ghasemi, Geoscience Australia\n'
        'Algorithm:\n'
        'In this study, the same functional form as Allen (2009) is '
        'adopted o express fatality rate as a function of intensity '
        '(see Eq. 10 in the report). The Matlab built-in function '
        '(fminsearch) for  Nelder-Mead algorithm was used to estimate '
        'the model parameters. The objective function (L2G norm) that '
        'is minimized during the optimisation is the same as the one '
        'used by Jaiswal et al. (2010).\n'
        'The coefficients used in the indonesian model are x=0.62275231, '
        'y=8.03314466, zeta=2.15')

    hazard_input = tr(
        'A hazard raster layer where each cell represents MMI ground shaking.')
    exposure_input = tr(
        'Raster layer where each cell represents the population density.')

    defaults = get_defaults()

    parameters = OrderedDict([
        ('x', 0.62275231), ('y', 8.03314466),  # Model coefficients
        # Rates of people displaced for each MMI level
        ('displacement_rate', {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 1.0,
                               7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0}),
        ('mmi_range', range(2, 10)),
        ('step', 0.5),
        # Threshold below which layer should be transparent
        ('tolerance', 0.01),
        ('calculate_displaced_people', True),
        ('postprocessors', OrderedDict([
            ('Gender', {'on': True}),
            ('Age', {
                'on': True,
                'params': OrderedDict([
                    ('youth_ratio', defaults['YOUTH_RATIO']),
                    ('adult_ratio', defaults['ADULT_RATIO']),
                    ('elder_ratio', defaults['ELDER_RATIO'])])}),
            ('MinimumNeeds', {'on': True})])),
        ('minimum needs', default_minimum_needs())])

    def fatality_rate(self, mmi):
        """
        ITB method to compute fatality rate
        :param mmi:
        """
        # As per email discussion with Ole, Trevor, Hadi, mmi < 4 will have
        # a fatality rate of 0 - Tim
        if mmi < 4:
            return 0

        x = self.parameters['x']
        y = self.parameters['y']
        return numpy.power(10.0, x * mmi - y)

    def run(self, layers):
        """Indonesian Earthquake Fatality Model

        Input:

        :param layers: List of layers expected to contain,

                my_hazard: Raster layer of MMI ground shaking

                my_exposure: Raster layer of population density
        """

        impact_keywords = ImpactKeywords()
        impact_keywords.set_function_details(self)
        impact_keywords.set_title(tr('Estimated displaced population per cell'))

        displacement_rate = self.parameters['displacement_rate']

        # Tolerance for transparency
        tolerance = self.parameters['tolerance']

        # Extract input layers
        intensity = get_hazard_layer(layers)
        population = get_exposure_layer(layers)

        impact_keywords.set_provenance_layer(intensity, 'impact_layer')
        impact_keywords.set_provenance_layer(population, 'exposure_layer')
        impact_keywords.set_impact_assesment('population', 'earthquake')

        question = get_question(intensity.get_name(),
                                population.get_name(),
                                self)

        # Extract data grids
        my_hazard = intensity.get_data()   # Ground Shaking
        my_exposure = population.get_data(scaling=True)  # Population Density

        # Calculate population affected by each MMI level
        # FIXME (Ole): this range is 2-9. Should 10 be included?

        mmi_range = self.parameters['mmi_range']
        number_of_exposed = {}
        number_of_displaced = {}
        number_of_fatalities = {}

        # Calculate fatality rates for observed Intensity values (my_hazard
        # based on ITB power model
        R = numpy.zeros(my_hazard.shape)
        for mmi in mmi_range:
            # Identify cells where MMI is in class i and
            # count population affected by this shake level
            I = numpy.where(
                (my_hazard > mmi - self.parameters['step']) * (
                    my_hazard <= mmi + self.parameters['step']),
                my_exposure, 0)

            # Calculate expected number of fatalities per level
            fatality_rate = self.fatality_rate(mmi)

            F = fatality_rate * I

            # Calculate expected number of displaced people per level
            try:
                D = displacement_rate[mmi] * I
            except KeyError, e:
                msg = 'mmi = %i, I = %s, Error msg: %s' % (mmi, str(I), str(e))
                # noinspection PyExceptionInherit
                raise InaSAFEError(msg)

            # Adjust displaced people to disregard fatalities.
            # Set to zero if there are more fatalities than displaced.
            D = numpy.where(D > F, D - F, 0)

            # Sum up numbers for map
            R += D   # Displaced

            # Generate text with result for this study
            # This is what is used in the real time system exposure table
            number_of_exposed[mmi] = numpy.nansum(I.flat)
            number_of_displaced[mmi] = numpy.nansum(D.flat)
            # noinspection PyUnresolvedReferences
            number_of_fatalities[mmi] = numpy.nansum(F.flat)

        # Set resulting layer to NaN when less than a threshold. This is to
        # achieve transparency (see issue #126).
        R[R < tolerance] = numpy.nan

        # Total statistics
        total = int(round(numpy.nansum(my_exposure.flat) / 1000) * 1000)

        # Compute number of fatalities
        fatalities = int(round(numpy.nansum(number_of_fatalities.values())
                               / 1000)) * 1000
        # As per email discussion with Ole, Trevor, Hadi, total fatalities < 50
        # will be rounded down to 0 - Tim
        if fatalities < 50:
            fatalities = 0

        # Compute number of people displaced due to building collapse
        displaced = int(round(numpy.nansum(number_of_displaced.values())
                              / 1000)) * 1000

        breakdown = ImpactBreakdown(
            [tr('Fatalities'), tr('People displaced'), tr('Total population')],
            [tr('population')])
        breakdown[tr('Fatalities'), tr('population')] = fatalities
        if self.parameters['calculate_displaced_people']:
            breakdown[tr('People displaced'), tr('population')] = displaced
        else:
            breakdown[tr('People displaced'), tr('population')] = 0
        breakdown[tr('Total population'), tr('population')] = int(total)
        impact_keywords.set_impact_breakdown(breakdown)

        # Calculate estimated needs based on BNPB Perka 7/2008 minimum bantuan
        minimum_needs = self.parameters['minimum needs']
        needs = evacuated_population_weekly_needs(
            displaced, minimum_needs, detailed=True)
        impact_keywords.set_minimum_needs(needs)

        table_formatter = TableSelector(impact_keywords)

       # Result
        table = table_formatter()
        impact_summary = table.toNewlineFreeString()
        impact_table = impact_summary

        # check for zero impact
        if numpy.nanmax(R) == 0 == numpy.nanmin(R):
            table_body = [
                question,
                TableRow([tr('Fatalities'), '%s' % format_int(fatalities)],
                         header=True)]
            my_message = Table(table_body).toNewlineFreeString()
            raise ZeroImpactException(my_message)

        # Create style
        colours = ['#EEFFEE', '#FFFF7F', '#E15500', '#E4001B', '#730000']
        classes = create_classes(R.flat[:], len(colours))
        interval_classes = humanize_class(classes)
        style_classes = []
        for i in xrange(len(colours)):
            style_class = dict()
            style_class['label'] = create_label(interval_classes[i])
            style_class['quantity'] = classes[i]
            if i == 0:
                transparency = 100
            else:
                transparency = 30
            style_class['transparency'] = transparency
            style_class['colour'] = colours[i]
            style_classes.append(style_class)

        style_info = dict(target_field=None,
                          style_classes=style_classes,
                          style_type='rasterStyle')

        # For printing map purpose
        map_title = tr('Earthquake impact to population')
        legend_notes = tr('Thousand separator is represented by %s' %
                          get_thousand_separator())
        legend_units = tr('(people per cell)')
        legend_title = tr('Population density')

        # Create raster object and return
        L = Raster(R,
                   projection=population.get_projection(),
                   geotransform=population.get_geotransform(),
                   keywords={'impact_summary': impact_summary,
                             'total_population': total,
                             'total_fatalities': fatalities,
                             'fatalities_per_mmi': number_of_fatalities,
                             'exposed_per_mmi': number_of_exposed,
                             'displaced_per_mmi': number_of_displaced,
                             'impact_table': impact_table,
                             'map_title': map_title,
                             'legend_notes': legend_notes,
                             'legend_units': legend_units,
                             'legend_title': legend_title},
                   name=tr('Estimated displaced population per cell'),
                   style_info=style_info)

        return L
