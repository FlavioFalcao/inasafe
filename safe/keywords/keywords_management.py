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
from collections import OrderedDict

from safe.common.utilities import ugettext as tr


def current_version():
    """Get the current version of the JSON Keywords.

    :return: The version number
    :rtype: int
    """
    return 1


class ImpactBreakdown(object):
    """A general impact breakdown.
    """
    def __init__(
            self, categories, attributes, category_label=None):
        """A category type breakdown of affected population/buildings or other.

        Creating a 'table' with columns defined by categories and rows
        defined by attributes. The implementation makes use of ordered dicts
        in both these cases

        :param categories: The categories that the breakdown consists of.
        :type categories: list

        :param attributes: The attributes in a category
        :type attributes: list

        :param category_label: The title that should be used for the category
        """
        self.category_label = category_label
        self.categories = categories
        self.attributes = attributes
        self.data = OrderedDict()
        for category in categories:
            self.data[category] = OrderedDict(
                zip(attributes, [None] * len(attributes)))

    def __getitem__(self, keys):
        """Get a specific element based on their category and attribute

        Make the object behave like a dict

        :param keys: The category and attribute of the breakdown
        :type keys: list

        :return: returns the value of the category attribute
        """
        category, attribute = keys
        return self.data[category][attribute]

    def __setitem__(self, keys, value):
        """Set a specific element based on their category and attribute

        Make the object behave like a dict

        :param keys: The category and attribute of the breakdown
        :type keys: list
        """
        category, attribute = keys
        self.data[category][attribute] = value

    def get_categories(self):
        """Get the categories by name of this impact breakdown

        :return: The categories that this impact has.
        :rtype: list
        """
        return self.categories

    def get_attributes(self):
        """Get the attributes by name of this impact breakdown

        :return: The attributes that this impact has.
        :rtype: list
        """
        return self.attributes

    def serialize(self):
        """Convert this object into a serialized version.

        :return: The content of this object.
        :rtype: OrderedDict
        """
        return OrderedDict([
            ('category_label', self.category_label),
            ('data', self.data),
            ('categories', self.categories),
            ('attributes', self.attributes)])


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
        self.post_processing = layer_data.get("post_processing", None)
        self.impact_breakdown = layer_data.get("impact_breakdown", None)
        self.layer_type = "impact"

    def serialize(self):
        """Serialize the content of the keywords layer into a python structure.

        :return: Content of object.
        :rtype: dict
        """
        serialized_data = OrderedDict()
        if self.function_details:
            serialized_data['function_details'] = self.function_details
        if self.impact_assessment:
            serialized_data['impact_assessment'] = self.impact_assessment
        if self.minimum_needs:
            serialized_data['minimum_needs'] = self.minimum_needs
        if self.post_processing:
            serialized_data['post_processing'] = self.post_processing
        if self.impact_breakdown:
            serialized_data['impact_breakdown'] = (
                self.impact_breakdown.serialize())
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


    def set_title(self, title):
        self.title = title

    def set_impact_breakdown(self, impact_breakdown):
        self.impact_breakdown = impact_breakdown


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
        serialized_data = OrderedDict()
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
        serialized_data = OrderedDict()
        return serialized_data

# Aggregation Layer


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
        # This is to support sublayers
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
        # Oredered Dict
        serialized_data = OrderedDict(('VERSION', self.version))
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

    def __getattr__(self, method):
        """ Hide the primary layer method calls.
        :param method: This is the name of the method in the primary layer.
        :return: the method required.
        """
        if hasattr(self.primary_layer, method):
            return getattr(self.primary_layer, method)
        else:
            raise AttributeError


class ImpactKeywords(Keywords):
    """A new keywords object with an empty primary layer of type Impact.
    """

    def __init__(self):
        super(ImpactKeywords, self).__init__()
        self.primary_layer = KeywordsLayerImpact({})
