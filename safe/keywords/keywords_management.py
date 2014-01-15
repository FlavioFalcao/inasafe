# -*- coding: utf-8 -*-
"""**Handle JSON keywords file.**

Classes to handle the creation and ingestion of keywords data in JASON format.
"""
__author__ = 'cchristelis@gmail.com'
__version__ = '0.1'
__date__ = '04/11/2013'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')
from exceptions import ValueError
import json

from safe.common.utilities import ugettext as tr


def current_version():
    """Get the current version of the JSON Keywords.

    :return: The version number
    :rtype: int
    """
    return 1


class KeywordsLayer(object):
    """The abstract class for managing the layer keywords.

    :param layer_data: The layer data.
    :type layer_data: dict

    :param version: The version which the keywords are at.
    :type version: int
    """

    def __init__(self, layer_data, version):
        self.version = version
        self.title = layer_data.get('title', None)

    def get_version(self):
        """Get the keyword layer's version

        :return: The keyword layer object's version.
        :rtype: int
        """
        return self.version


class KeywordsLayerImpact(KeywordsLayer):
    """Manage Keywords specific to an impact layer.

    :param layer_data: The layer data.
    :type layer_data: dict

    :param version: The version which the keywords are at. Default to current
     version.
    :type version: int
    """

    def __init__(self, layer_data, version=current_version()):
        super(KeywordsLayerImpact, self).__init__(layer_data, version)
        self.function_details = layer_data.get("function_details", None)
        self.impact_assessment = layer_data.get("impact_assessment", None)
        self.minimum_needs = layer_data.get("minimum_needs", None)
        self.buildings_breakdown = layer_data.get("buildings_breakdown", None)
        self.post_processing = layer_data.get("post_processing", None)
        self.layer_type = "impact"

    def serialize(self):
        """Serialize the content of the keywords layer into a python structure.

        :return: Content of object.
        :rtype: dict
        """
        serialized_data = {}
        if self.function_details:
            serialized_data['function_details'] = self.function_details
        if self.impact_assessment:
            serialized_data['impact_assessment'] = self.impact_assessment
        if self.minimum_needs:
            serialized_data['minimum_needs'] = self.minimum_needs
        if self.buildings_breakdown:
            serialized_data['buildings_breakdown'] = self.buildings_breakdown
        if self.post_processing:
            serialized_data['post_processing'] = self.post_processing
        return serialized_data

    def set_impact_assesment(self, exposure_subcategory, hazard_subcategory):
        """Set generic impact assessment details, based on exposure type and
        hazard type.

        :param exposure_subcategory: The exposure subcatagory.
        :type exposure_subcategory: str

        :param hazard_subcategory: The hazard subcatagory.
        :type hazard_subcategory: str
        """
        self.impact_assessment = {
            "exposure_subcategory": exposure_subcategory,
            "hazard_subcategory": hazard_subcategory}
        if hazard_subcategory == "flood":
            self.impact_assessment["hazard_units"] = "wet/dry"

    def set_impact_assesment_buildings(
            self, hazard_subcategory,
            buildings_total, buildings_affected):
        """Set impact assessment details for building impact.

        :param hazard_subcategory: The type of hazard.
        :type hazard_subcategory: str

        :param buildings_total: Total building types.
        :type buildings_total: dict

        :param buildings_affected: Number of affected buildings by type. This
         is a dict of dicts
        :type buildings_affected: dict
        """
        self.set_impact_assesment(
            'buildings', hazard_subcategory)
        self.impact_assessment['total_buildings'] = sum(
            buildings_total.values())
        for key in buildings_affected:
            self.impact_assessment[key] = sum(
                buildings_affected[key].values())

    def set_impact_assesment_population(
            self, hazard_subcategory,
            affected_population, evacuated_population, total_population,
            additional=None):
        """Set impact assessment details for population impact.

        :param hazard_subcategory: The type of hazard.
        :type hazard_subcategory: str

        :param affected_population: The number of affected population
        :type affected_population: int

        :param evacuated_population: The number of evacuated population
        :type evacuated_population: int

        :param total_population: The total population
        :type total_population: int

        :param additional: A dictionary of additional assessment data.
        :type additional: dict, None
        """
        self.set_impact_assesment(
            'population', hazard_subcategory)
        self.impact_assessment['affected_population'] = affected_population
        self.impact_assessment['evacuated_population'] = evacuated_population
        self.impact_assessment['total_population'] = total_population
        if additional:
            for key, value in additional.items():
                self.impact_assessment[key] = value

    def set_minimum_needs(self, minimum_needs):
        self.minimum_needs = minimum_needs

    def set_function_details(self, impact_function):
        self.function_details = {
            "impact_function_name": impact_function.__class__.__name__,
            "impact_function_id": impact_function.function_id,
            "synopsis": impact_function.synopsis,
            "title": impact_function.title,
            "parameters": impact_function.parameters,
            "description": impact_function.detailed_description,
            "hazard": impact_function.hazard_input,
            "exposure": impact_function.exposure_input}
        for attr in ["author", "rating", "citation", "limitation"]:
            if hasattr(impact_function, attr):
                self.function_details[attr] = getattr(impact_function, attr)

    def set_buildings_breakdown(self, buildings, buildings_breakdown):
        self.buildings_breakdown = {}
        for building_type in buildings:
            building_type = building_type.replace('_', ' ')
            building_type = tr(building_type)
            self.buildings_breakdown[building_type] = {
                "total": buildings[building_type]
            }
            for key in buildings_breakdown:
                self.buildings_breakdown[building_type][key] = (
                    buildings_breakdown[key][building_type])


    def set_title(self, title):
        self.title = title


class KeywordsLayerExposure(KeywordsLayer):
    """Manage Keywords specific to an exposure layer.

    :param layer_data: The layer data.
    :type layer_data: dict

    :param version: The version which the keywords are at. Default to current
     version.
    :type version: int
    """

    def __init__(self, layer_data, version=current_version()):
        super(KeywordsLayerExposure, self).__init__(layer_data, version)
        self.layer_type = "exposure"

    def serialize(self):
        """Serialize the content of the keywords layer into a python structure.

        :return: Content of object.
        :rtype: dict
        """
        serialized_data = {}
        return serialized_data


class KeywordsLayerHazard(KeywordsLayer):
    """Manage Keywords specific to a hazard layer.

    :param layer_data: The layer data.
    :type layer_data: dict

    :param version: The version which the keywords are at. Default to current
     version.
    :type version: int
    """

    def __init__(self, layer_data, version=current_version()):
        super(KeywordsLayerHazard, self).__init__(layer_data, version)
        self.layer_type = "hazard"

    def serialize(self):
        """Serialize the content of the keywords layer into a python structure.

        :return: Content of object.
        :rtype: dict
        """
        serialized_data = {}
        return serialized_data


class Keywords(object):
    """A abstraction of the keywords file

    :param data: json dump or Nothing for a new keywords object.
    :type data: str
    """

    def __init__(self, data=None):
        if data:
            try:
                data = json.loads(data)
            except ValueError:
                data = {}
        else:
            data = {}
        self.version = data.get('VERSION', current_version())
        self.publisher = data.get('publisher', None)
        self.attribution = data.get('attribution', None)
        self.provenance = data.get('provenance', {})
        self.metrics = data.get('metrics', None)
        for layer_label in ['primary_layer', 'secondary_layer']:
            if layer_label not in data:
                setattr(self, layer_label, None)
                continue
            layer_data = data.get(layer_label, None)
            if layer_data['layer_type'] == 'impact':
                layer = KeywordsLayerImpact(data, self.version)
            elif layer_data['layer_type'] == 'exposure':
                layer = KeywordsLayerExposure(data, self.version)
            elif layer_data['layer_type'] == 'hazard':
                layer = KeywordsLayerHazard(data, self.version)
            else:
                layer = None
            setattr(self, layer_label, layer)

    def serialize(self):
        """Serialize the content of the keywords object to a python structure.

        :return: Content of object.
        :rtype: dict
        """
        serialized_data = {'VERSION': self.version}
        if self.publisher:
            serialized_data['publisher'] = self.publisher
        if self.attribution:
            serialized_data['attribution'] = self.attribution
        if self.provenance:
            serialized_data['provenance'] = self.provenance
        if self.metrics:
            serialized_data['metrics'] = self.metrics
        if self.primary_layer:
            serialized_data['primary_layer'] = self.primary_layer.serialize()
        if self.secondary_layer:
            serialized_data[
                'secondary_layer'] = self.secondary_layer.serialize()
        return serialized_data

    def json_dump(self):
        """Converts the keywords object into a JSON dump.

        :return: json dump.
        :rtype: str
        """
        return json.dumps(self.serialize())

    def get_version(self):
        """Get the keyword's version

        :return: The keyword object's version.
        :rtype: int
        """
        return self.version

    def set_provenance_layer(self, layer, layer_type):
        """Set the provenance from the given layer information.

        :param layer: The layer that is source
        :type layer: Vector, Raster

        :param layer_type: They type that this layer is.
        :type layer_type: str
        """
        self.provenance[layer_type] = {
            'path': layer.get_filename(),
            'name': layer.get_name(),
            'type': 'vector' if layer.is_vector else 'raster'}
        if 'attribution' in layer.keywords:
            self.provenance['attribution'] = layer.keywords['attribution']


class ImpactKeywords(Keywords):
    """A new keywords object with an empty primary layer of type Impact.
    """

    def __init__(self):
        super(ImpactKeywords, self).__init__()
        self.primary_layer = KeywordsLayerImpact({})
