"""
InaSAFE Disaster risk assessment tool developed by AusAid -
  **IS Utilitles implementation.**

Contact : ole.moller.nielsen@gmail.com

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'tim@linfiniti.com'
__revision__ = '$Format:%H$'
__date__ = '29/01/2011'
__copyright__ = 'Copyright 2012, Australia Indonesia Facility for '
__copyright__ += 'Disaster Reduction'

import os
import sys
import traceback
import logging
import math
import numpy
import uuid

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QCoreApplication

from qgis.core import (QGis,
                       QgsRasterLayer,
                       QgsMapLayer,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,
                       QgsGraduatedSymbolRendererV2,
                       QgsSymbolV2,
                       QgsRendererRangeV2,
                       QgsSymbolLayerV2Registry,
                       QgsColorRampShader,
                       QgsRasterTransparency,
                       QgsVectorLayer,
                       QgsFeature
                       )

from safe_interface import temp_dir

from safe_qgis.exceptions import (StyleError,
                                  MethodUnavailableError,
                                  MemoryLayerCreationError)

from safe_qgis.safe_interface import DEFAULTS, safeTr, get_version

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'third_party')))
# pylint: disable=F0401
from raven.handlers.logging import SentryHandler
from raven import Client
# pylint: enable=F0401

#do not remove this even if it is marked as unused by your IDE
#resources are used by htmlfooter and header the comment will mark it unused
#for pylint
import safe_qgis.resources  # pylint: disable=W0611

LOGGER = logging.getLogger('InaSAFE')


def setVectorStyle(theQgisVectorLayer, theStyle):
    """Set QGIS vector style based on InaSAFE style dictionary.

    For **opaque** a value of **0** can be used. For **fully transparent**, a
    value of **100** can be used. The calling function should take care to
    scale the transparency level to between 0 and 100.

    Args:
        * theQgisVectorLayer: QgsMapLayer
        * theStyle: dict - Dictionary of the form as in the example below

    Returns:
        None - Sets and saves style for theQgisVectorLayer

    Raises:
        None

    Example:

        {'target_field': 'DMGLEVEL',
        'style_classes':
        [{'transparency': 1, 'max': 1.5, 'colour': '#fecc5c',
          'min': 0.5, 'label': 'Low damage', 'size' : 1},
        {'transparency': 55, 'max': 2.5, 'colour': '#fd8d3c',
         'min': 1.5, 'label': 'Medium damage', 'size' : 1},
        {'transparency': 80, 'max': 3.5, 'colour': '#f31a1c',
         'min': 2.5, 'label': 'High damage', 'size' : 1}]}

        .. note:: The transparency and size keys are optional. Size applies
           to points only.

    """
    myTargetField = theStyle['target_field']
    myClasses = theStyle['style_classes']
    myGeometryType = theQgisVectorLayer.geometryType()

    myRangeList = []
    for myClass in myClasses:
        # Transparency 100: transparent
        # Transparency 0: opaque
        mySize = 2  # mm
        if 'size' in myClass:
            mySize = myClass['size']
        myTransparencyPercent = 0
        if 'transparency' in myClass:
            myTransparencyPercent = myClass['transparency']

        if 'min' not in myClass:
            raise StyleError('Style info should provide a "min" entry')
        if 'max' not in myClass:
            raise StyleError('Style info should provide a "max" entry')

        try:
            myMin = float(myClass['min'])
        except TypeError:
            raise StyleError(
                'Class break lower bound should be a number.'
                'I got %s' % myClass['min'])

        try:
            myMax = float(myClass['max'])
        except TypeError:
            raise StyleError('Class break upper bound should be a number.'
                             'I got %s' % myClass['max'])

        myColour = myClass['colour']
        myLabel = myClass['label']
        myColour = QtGui.QColor(myColour)
        mySymbol = QgsSymbolV2.defaultSymbol(myGeometryType)
        myColourString = "%s, %s, %s" % (
                         myColour.red(),
                         myColour.green(),
                         myColour.blue())
        # Work around for the fact that QgsSimpleMarkerSymbolLayerV2
        # python bindings are missing from the QGIS api.
        # .. see:: http://hub.qgis.org/issues/4848
        # We need to create a custom symbol layer as
        # the border colour of a symbol can not be set otherwise
        myRegistry = QgsSymbolLayerV2Registry.instance()
        if myGeometryType == QGis.Point:
            myMetadata = myRegistry.symbolLayerMetadata('SimpleMarker')
            # note that you can get a list of available layer properties
            # that you can set by doing e.g.
            # QgsSimpleMarkerSymbolLayerV2.properties()
            mySymbolLayer = myMetadata.createSymbolLayer({'color_border':
                                                          myColourString})
            mySymbolLayer.setSize(mySize)
            mySymbol.changeSymbolLayer(0, mySymbolLayer)
        elif myGeometryType == QGis.Polygon:
            myMetadata = myRegistry.symbolLayerMetadata('SimpleFill')
            mySymbolLayer = myMetadata.createSymbolLayer({'color_border':
                                                          myColourString})
            mySymbol.changeSymbolLayer(0, mySymbolLayer)
        else:
            # for lines we do nothing special as the property setting
            # below should give us what we require.
            pass

        mySymbol.setColor(myColour)
        # .. todo:: Check that vectors use alpha as % otherwise scale TS
        # Convert transparency % to opacity
        # alpha = 0: transparent
        # alpha = 1: opaque
        alpha = 1 - myTransparencyPercent / 100.0
        mySymbol.setAlpha(alpha)
        myRange = QgsRendererRangeV2(myMin,
                                     myMax,
                                     mySymbol,
                                     myLabel)
        myRangeList.append(myRange)

    myRenderer = QgsGraduatedSymbolRendererV2('', myRangeList)
    myRenderer.setMode(QgsGraduatedSymbolRendererV2.EqualInterval)
    myRenderer.setClassAttribute(myTargetField)
    theQgisVectorLayer.setRendererV2(myRenderer)
    theQgisVectorLayer.saveDefaultStyle()


def setRasterStyle(theQgsRasterLayer, theStyle):
    """Set QGIS raster style based on InaSAFE style dictionary.

    This function will set both the colour map and the transparency
    for the passed in layer.

    Args:
        * theQgsRasterLayer: QgsRasterLayer
        * style: dict - Dictionary of the form as in the example below.

    Example:
        style_classes = [dict(colour='#38A800', quantity=2, transparency=0),
                         dict(colour='#38A800', quantity=5, transparency=50),
                         dict(colour='#79C900', quantity=10, transparency=50),
                         dict(colour='#CEED00', quantity=20, transparency=50),
                         dict(colour='#FFCC00', quantity=50, transparency=34),
                         dict(colour='#FF6600', quantity=100, transparency=77),
                         dict(colour='#FF0000', quantity=200, transparency=24),
                         dict(colour='#7A0000', quantity=300, transparency=22)]

    Returns:
        list: RangeList
        list: TransparencyList
    """
    myNewStyles = _addMinMaxToStyle(theStyle['style_classes'])
    # test if QGIS 1.8.0 or older
    # see issue #259
    if qgisVersion() <= 10800:
        LOGGER.debug('Rendering raster using <= 1.8 styling')
        return _setLegacyRasterStyle(theQgsRasterLayer, myNewStyles)
    else:
        LOGGER.debug('Rendering raster using 2+ styling')
        return _setNewRasterStyle(theQgsRasterLayer, myNewStyles)


def _addMinMaxToStyle(theStyle):
    """Add a min and max to each style class in a style dictionary.

    When InaSAFE provides style classes they are specific values, not ranges.
    However QGIS wants to work in ranges, so this helper will address that by
    updating the dictionary to include a min max value for each class.

    It is assumed that we will start for 0 as the min for the first class
    and the quantity of each class shall constitute the max. For all other
    classes , min shall constitute the smalles increment to a float that can
    meaningfully be made by python (as determined by numpy.nextafter()).

    Args:
        style: list - A list of dictionaries of the form as in the example
            below.

    Returns:
        dict: A new dictionary list with min max attributes added to each
            entry.

    Example input:

        style_classes = [dict(colour='#38A800', quantity=2, transparency=0),
                         dict(colour='#38A800', quantity=5, transparency=50),
                         dict(colour='#79C900', quantity=10, transparency=50),
                         dict(colour='#CEED00', quantity=20, transparency=50),
                         dict(colour='#FFCC00', quantity=50, transparency=34),
                         dict(colour='#FF6600', quantity=100, transparency=77),
                         dict(colour='#FF0000', quantity=200, transparency=24),
                         dict(colour='#7A0000', quantity=300, transparency=22)]

    Example output:

        style_classes = [dict(colour='#38A800', quantity=2, transparency=0,
                              min=0, max=2),
                         dict(colour='#38A800', quantity=5, transparency=50,
                              min=2.0000000000002, max=5),
                         ),
                         dict(colour='#79C900', quantity=10, transparency=50,
                              min=5.0000000000002, max=10),),
                         dict(colour='#CEED00', quantity=20, transparency=50,
                              min=5.0000000000002, max=20),),
                         dict(colour='#FFCC00', quantity=50, transparency=34,
                              min=20.0000000000002, max=50),),
                         dict(colour='#FF6600', quantity=100, transparency=77,
                              min=50.0000000000002, max=100),),
                         dict(colour='#FF0000', quantity=200, transparency=24,
                              min=100.0000000000002, max=200),),
                         dict(colour='#7A0000', quantity=300, transparency=22,
                              min=200.0000000000002, max=300),)]
    """
    myNewStyles = []
    myLastMax = 0.0
    for myClass in theStyle:
        myQuantity = float(myClass['quantity'])
        myClass['min'] = myLastMax
        myClass['max'] = myQuantity
        if myQuantity == myLastMax:
            # skip it as it does not represent a class increment
            continue
        myLastMax = numpy.nextafter(myQuantity, sys.float_info.max)
        myNewStyles.append(myClass)
    return myNewStyles


def _setLegacyRasterStyle(theQgsRasterLayer, theStyle):
    """Set QGIS raster style based on InaSAFE style dictionary for QGIS < 2.0.

    This function will set both the colour map and the transparency
    for the passed in layer.

    Args:
        * theQgsRasterLayer: QgsRasterLayer.
        * style: List - of the form as in the example below.

    Returns:
        * list: RangeList
        * list: TransparencyList

    Example:

        style_classes = [dict(colour='#38A800', quantity=2, transparency=0),
                         dict(colour='#38A800', quantity=5, transparency=50),
                         dict(colour='#79C900', quantity=10, transparency=50),
                         dict(colour='#CEED00', quantity=20, transparency=50),
                         dict(colour='#FFCC00', quantity=50, transparency=34),
                         dict(colour='#FF6600', quantity=100, transparency=77),
                         dict(colour='#FF0000', quantity=200, transparency=24),
                         dict(colour='#7A0000', quantity=300, transparency=22)]

    .. note:: There is currently a limitation in QGIS in that
       pixel transparency values can not be specified in ranges and
       consequently the opacity is of limited value and seems to
       only work effectively with integer values.

    """
    theQgsRasterLayer.setDrawingStyle(QgsRasterLayer.PalettedColor)
    LOGGER.debug(theStyle)
    myRangeList = []
    myTransparencyList = []
    # Always make 0 pixels transparent see issue #542
    myPixel = QgsRasterTransparency.TransparentSingleValuePixel()
    myPixel.pixelValue = 0.0
    myPixel.percentTransparent = 100
    myTransparencyList.append(myPixel)
    myLastValue = 0
    for myClass in theStyle:
        LOGGER.debug('Evaluating class:\n%s\n' % myClass)
        myMax = myClass['quantity']
        myColour = QtGui.QColor(myClass['colour'])
        myLabel = QtCore.QString()
        if 'label' in myClass:
            myLabel = QtCore.QString(myClass['label'])
        myShader = QgsColorRampShader.ColorRampItem(myMax, myColour, myLabel)
        myRangeList.append(myShader)

        if math.isnan(myMax):
            LOGGER.debug('Skipping class.')
            continue

        # Create opacity entries for this range
        myTransparencyPercent = 0
        if 'transparency' in myClass:
            myTransparencyPercent = int(myClass['transparency'])
        if myTransparencyPercent > 0:
            # Always assign the transparency to the class' specified quantity
            myPixel = QgsRasterTransparency.TransparentSingleValuePixel()
            myPixel.pixelValue = myMax
            myPixel.percentTransparent = myTransparencyPercent
            myTransparencyList.append(myPixel)

            # Check if range extrema are integers so we know if we can
            # use them to calculate a value range
            if (myLastValue == int(myLastValue)) and (myMax == int(myMax)):
                # Ensure that they are integers
                # (e.g 2.0 must become 2, see issue #126)
                myLastValue = int(myLastValue)
                myMax = int(myMax)

                # Set transparencies
                myRange = range(myLastValue, myMax)
                for myValue in myRange:
                    myPixel = \
                        QgsRasterTransparency.TransparentSingleValuePixel()
                    myPixel.pixelValue = myValue
                    myPixel.percentTransparent = myTransparencyPercent
                    myTransparencyList.append(myPixel)
                    #myLabel = myClass['label']

    # Apply the shading algorithm and design their ramp
    theQgsRasterLayer.setColorShadingAlgorithm(
        QgsRasterLayer.ColorRampShader)
    myFunction = theQgsRasterLayer.rasterShader().rasterShaderFunction()
    # Discrete will shade any cell between maxima of this break
    # and minima of previous break to the colour of this break
    myFunction.setColorRampType(QgsColorRampShader.DISCRETE)
    myFunction.setColorRampItemList(myRangeList)

    # Now set the raster transparency
    theQgsRasterLayer.rasterTransparency()\
        .setTransparentSingleValuePixelList(myTransparencyList)

    theQgsRasterLayer.saveDefaultStyle()
    return myRangeList, myTransparencyList


def _setNewRasterStyle(theQgsRasterLayer, theClasses):
    """Set QGIS raster style based on InaSAFE style dictionary for QGIS >= 2.0.

    This function will set both the colour map and the transparency
    for the passed in layer.

    Args:
        * theQgsRasterLayer: QgsRasterLayer
        * theClasses: List of the form as in the example below.

    Returns:
        * list: RangeList
        * list: TransparencyList

    Example:
        style_classes = [dict(colour='#38A800', quantity=2, transparency=0),
                         dict(colour='#38A800', quantity=5, transparency=50),
                         dict(colour='#79C900', quantity=10, transparency=50),
                         dict(colour='#CEED00', quantity=20, transparency=50),
                         dict(colour='#FFCC00', quantity=50, transparency=34),
                         dict(colour='#FF6600', quantity=100, transparency=77),
                         dict(colour='#FF0000', quantity=200, transparency=24),
                         dict(colour='#7A0000', quantity=300, transparency=22)]

    """
    # Note imports here to prevent importing on unsupported QGIS versions
    # pylint: disable=E0611
    # pylint: disable=W0621
    # pylint: disable=W0404
    from qgis.core import (QgsRasterShader,
                           QgsColorRampShader,
                           QgsSingleBandPseudoColorRenderer,
                           QgsRasterTransparency)
    # pylint: enable=E0611
    # pylint: enable=W0621
    # pylint: enable=W0404

    myRampItemList = []
    myTransparencyList = []
    LOGGER.debug(theClasses)
    for myClass in theClasses:

        LOGGER.debug('Evaluating class:\n%s\n' % myClass)

        if 'quantity' not in myClass:
            LOGGER.exception('Class has no quantity attribute')
            continue

        myMax = myClass['max']
        if math.isnan(myMax):
            LOGGER.debug('Skipping class - max is nan.')
            continue

        myMin = myClass['min']
        if math.isnan(myMin):
            LOGGER.debug('Skipping class - min is nan.')
            continue

        myColour = QtGui.QColor(myClass['colour'])
        myLabel = QtCore.QString()
        if 'label' in myClass:
            myLabel = QtCore.QString(myClass['label'])
        myRampItem = QgsColorRampShader.ColorRampItem(myMax, myColour, myLabel)
        myRampItemList.append(myRampItem)

        # Create opacity entries for this range
        myTransparencyPercent = 0
        if 'transparency' in myClass:
            myTransparencyPercent = int(myClass['transparency'])
        if myTransparencyPercent > 0:
            # Check if range extrema are integers so we know if we can
            # use them to calculate a value range
            myPixel = QgsRasterTransparency.TransparentSingleValuePixel()
            myPixel.min = myMin
            # We want it just a leeetle bit smaller than max
            # so that ranges are discrete
            myPixel.max = myMax
            myPixel.percentTransparent = myTransparencyPercent
            myTransparencyList.append(myPixel)

    myBand = 1  # gdal counts bands from base 1
    LOGGER.debug('Setting colour ramp list')
    myRasterShader = QgsRasterShader()
    myColorRampShader = QgsColorRampShader()
    myColorRampShader.setColorRampType(QgsColorRampShader.INTERPOLATED)
    myColorRampShader.setColorRampItemList(myRampItemList)
    LOGGER.debug('Setting shader function')
    myRasterShader.setRasterShaderFunction(myColorRampShader)
    LOGGER.debug('Setting up renderer')
    myRenderer = QgsSingleBandPseudoColorRenderer(
        theQgsRasterLayer.dataProvider(),
        myBand,
        myRasterShader)
    LOGGER.debug('Assigning renderer to raster layer')
    theQgsRasterLayer.setRenderer(myRenderer)

    LOGGER.debug('Setting raster transparency list')

    myRenderer = theQgsRasterLayer.renderer()
    myTransparency = QgsRasterTransparency()
    myTransparency.setTransparentSingleValuePixelList(myTransparencyList)
    myRenderer.setRasterTransparency(myTransparency)
    # For interest you can also view the list like this:
    #pix = t.transparentSingleValuePixelList()
    #for px in pix:
    #    print 'Min: %s Max %s Percent %s' % (
    #       px.min, px.max, px.percentTransparent)

    LOGGER.debug('Saving style as default')
    theQgsRasterLayer.saveDefaultStyle()
    LOGGER.debug('Setting raster style done!')
    return myRampItemList, myTransparencyList


def tr(theText):
    """We define a tr() alias here since the utilities implementation below
    is not a class and does not inherit from QObject.
    .. note:: see http://tinyurl.com/pyqt-differences
    Args:
       theText - string to be translated
    Returns:
       Translated version of the given string if available, otherwise
       the original string.
    """
    return QCoreApplication.translate('@default', theText)


def getExceptionWithStacktrace(theException, theHtml=False, theContext=None):
    """Convert exception into a string containing a stack trace.

    .. note: OS File path separators will be replaced with <wbr> which is a
        'soft wrap' (when theHtml=True)_that will ensure that long paths do not
        force the web frame to be very wide.

    Args:
        * theException: Exception object.
        * theHtml: Optional flag if output is to be wrapped as theHtml.
        * theContext: Optional theContext message.

    Returns:
        Exception: with stack trace info suitable for display.
    """

    myTraceback = ''.join(traceback.format_tb(sys.exc_info()[2]))

    if not theHtml:
        if str(theException) is None or str(theException) == '':
            myErrorMessage = (theException.__class__.__name__ + ' : ' +
                              tr('No details provided'))
        else:
            myErrorMessage = (theException.__class__.__name__ + ' : ' +
                              str(theException))
        return myErrorMessage + "\n" + myTraceback
    else:
        if str(theException) is None or str(theException) == '':
            myErrorMessage = ('<b>' + theException.__class__.__name__ +
                              '</b> : ' + tr('No details provided'))
        else:
            myWrappedMessage = str(theException).replace(os.sep,
                                                         '<wbr>' + os.sep)
            # If the message contained some html above has a side effect of
            # turning </foo> into <<wbr>/foo> and <hr /> into <hr <wbr>/>
            # so we need to revert that using the next two lines.
            myWrappedMessage = myWrappedMessage.replace('<<wbr>' + os.sep,
                                                        '<' + os.sep)
            myWrappedMessage = myWrappedMessage.replace('<wbr>' + os.sep + '>',
                                                        os.sep + '>')

            myErrorMessage = ('<b>' + theException.__class__.__name__ +
                              '</b> : ' + myWrappedMessage)

        myTraceback = (
            '<pre id="traceback" class="prettyprint"'
            ' style="display: none;">\n' + myTraceback + '</pre>')

        # Wrap string in theHtml
        s = '<table class="condensed">'
        if theContext is not None and theContext != '':
            s += ('<tr><th class="warning button-cell">'
                  + tr('Error:') + '</th></tr>\n'
                  '<tr><td>' + theContext + '</td></tr>\n')
        # now the string from the error itself
        s += (
            '<tr><th class="problem button-cell">'
            + tr('Problem:') + '</th></tr>\n'
            '<tr><td>' + myErrorMessage + '</td></tr>\n')
            # now the traceback heading
        s += ('<tr><th class="info button-cell" style="cursor:pointer;"'
              ' onclick="$(\'#traceback\').toggle();">'
              + tr('Click for Diagnostic Information:') + '</th></tr>\n'
              '<tr><td>' + myTraceback + '</td></tr>\n')
        s += '</table>'
        return s


def getWGS84resolution(theLayer):
    """Return resolution of raster layer in EPSG:4326

    Input
        theLayer: Raster layer
    Output
        resolution.

    If input layer is already in EPSG:4326, simply return the resolution
    If not, work it out based on EPSG:4326 representations of its extent
    """

    msg = tr(
        'Input layer to getWGS84resolution must be a raster layer. '
        'I got: %s' % str(theLayer.type())[1:-1])
    if not theLayer.type() == QgsMapLayer.RasterLayer:
        raise RuntimeError(msg)

    if theLayer.crs().authid() == 'EPSG:4326':
        # If it is already in EPSG:4326, simply use the native resolution
        myCellSize = theLayer.rasterUnitsPerPixel()
    else:
        # Otherwise, work it out based on EPSG:4326 representations of
        # its extent

        # Reproject extent to EPSG:4326
        myGeoCrs = QgsCoordinateReferenceSystem()
        myGeoCrs.createFromId(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
        myXForm = QgsCoordinateTransform(theLayer.crs(), myGeoCrs)
        myExtent = theLayer.extent()
        myProjectedExtent = myXForm.transformBoundingBox(myExtent)

        # Estimate cellsize
        myColumns = theLayer.width()
        myGeoWidth = abs(myProjectedExtent.xMaximum() -
                         myProjectedExtent.xMinimum())
        myCellSize = myGeoWidth / myColumns

    return myCellSize


def htmlHeader():
    """Get a standard html header for wrapping content in."""
    myFile = QtCore.QFile(':/plugins/inasafe/header.html')
    if not myFile.open(QtCore.QIODevice.ReadOnly):
        return '----'
    myStream = QtCore.QTextStream(myFile)
    myHeader = myStream.readAll()
    myFile.close()
    return myHeader


def htmlFooter():
    """Get a standard html footer for wrapping content in."""
    myFile = QtCore.QFile(':/plugins/inasafe/footer.html')
    if not myFile.open(QtCore.QIODevice.ReadOnly):
        return '----'
    myStream = QtCore.QTextStream(myFile)
    myFooter = myStream.readAll()
    myFile.close()
    return myFooter


def qgisVersion():
    """Get the version of QGIS
   Args:
       None
    Returns:
        QGIS Version where 10700 represents QGIS 1.7 etc.
    Raises:
       None
    """
    myVersion = None
    try:
        myVersion = unicode(QGis.QGIS_VERSION_INT)
    except AttributeError:
        myVersion = unicode(QGis.qgisVersion)[0]
    myVersion = int(myVersion)
    return myVersion


# TODO: move this to its own file? TS
class QgsLogHandler(logging.Handler):
    """A logging handler that will log messages to the QGIS logging console."""

    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self)

    def emit(self, theRecord):
        """Try to log the message to QGIS if available, otherwise do nothing.

        Args:
            theRecord: logging record containing whatever info needs to be
                logged.
        Returns:
            None
        Raises:
            None
        """
        try:
            #available from qgis 1.8
            from qgis.core import QgsMessageLog
            # Check logging.LogRecord properties for lots of other goodies
            # like line number etc. you can get from the log message.
            QgsMessageLog.logMessage(theRecord.getMessage(), 'InaSAFE', 0)

        except (MethodUnavailableError, ImportError):
            pass


def addLoggingHanderOnce(theLogger, theHandler):
    """A helper to add a handler to a logger, ensuring there are no duplicates.

    Args:
        * theLogger: logging.logger instance
        * theHandler: logging.Handler instance to be added. It will not be
            added if an instance of that Handler subclass already exists.

    Returns:
        bool: True if the logging handler was added

    Raises:
        None
    """
    myClassName = theHandler.__class__.__name__
    for myHandler in theLogger.handlers:
        if myHandler.__class__.__name__ == myClassName:
            return False

    theLogger.addHandler(theHandler)
    return True


def setupLogger(theLogFile=None, theSentryUrl=None):
    """Run once when the module is loaded and enable logging

    Args:
        * theLogFile: str - optional full path to a file to write logs to.
        * theSentryUrl: str - optional url to sentry api for remote logging.
            Defaults to http://c64a83978732474ea751d432ab943a6b
                :d9d8e08786174227b9dcd8a4c3f6e9da@sentry.linfiniti.com/5
            which is the sentry project for InaSAFE desktop.

    Returns: None

    Raises: None

    Borrowed heavily from this:
    http://docs.python.org/howto/logging-cookbook.html

    Use this to first initialise the logger (see safe/__init__.py)::

       from safe_qgis import utilities
       utilities.setupLogger()

    You would typically only need to do the above once ever as the
    safe modle is initialised early and will set up the logger
    globally so it is available to all packages / subpackages as
    shown below.

    In a module that wants to do logging then use this example as
    a guide to get the initialised logger instance::

       # The LOGGER is intialised in utilities.py by init
       import logging
       LOGGER = logging.getLogger('InaSAFE')

    Now to log a message do::

       LOGGER.debug('Some debug message')

    .. note:: The file logs are written to the inasafe user tmp dir e.g.:
       /tmp/inasafe/23-08-2012/timlinux/logs/inasafe.log

    """
    myLogger = logging.getLogger('InaSAFE')
    myLogger.setLevel(logging.DEBUG)
    myDefaultHanderLevel = logging.DEBUG
    # create formatter that will be added to the handlers
    myFormatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # create syslog handler which logs even debug messages
    # (ariel): Make this log to /var/log/safe.log instead of
    #               /var/log/syslog
    # (Tim) Ole and I discussed this - we prefer to log into the
    # user's temporary working directory.
    myTempDir = temp_dir('logs')
    myFilename = os.path.join(myTempDir, 'inasafe.log')
    if theLogFile is None:
        myFileHandler = logging.FileHandler(myFilename)
    else:
        myFileHandler = logging.FileHandler(theLogFile)
    myFileHandler.setLevel(myDefaultHanderLevel)
    # create console handler with a higher log level
    myConsoleHandler = logging.StreamHandler()
    myConsoleHandler.setLevel(logging.INFO)

    myQGISHandler = QgsLogHandler()

    # Sentry handler - this is optional hence the localised import
    # It will only log if pip install raven. If raven is available
    # logging messages will be sent to http://sentry.linfiniti.com
    # We will log exceptions only there. You need to either:
    #  * Set env var 'INSAFE_SENTRY=1' present (value can be anything)
    #  * Enable the 'help improve InaSAFE by submitting errors to a remove
    #    server' option in InaSAFE options dialog
    # before this will be enabled.
    mySettings = QtCore.QSettings()
    myFlag = mySettings.value('inasafe/useSentry', False).toBool()
    if 'INASAFE_SENTRY' in os.environ or myFlag:
        if theSentryUrl is None:
            myClient = Client(
                'http://c64a83978732474ea751d432ab943a6b'
                ':d9d8e08786174227b9dcd8a4c3f6e9da@sentry.linfiniti.com/5')
        else:
            myClient = Client(theSentryUrl)
        mySentryHandler = SentryHandler(myClient)
        mySentryHandler.setFormatter(myFormatter)
        mySentryHandler.setLevel(logging.ERROR)
        if addLoggingHanderOnce(myLogger, mySentryHandler):
            myLogger.debug('Sentry logging enabled')
    else:
        myLogger.debug('Sentry logging disabled')
    #Set formatters
    myFileHandler.setFormatter(myFormatter)
    myConsoleHandler.setFormatter(myFormatter)
    myQGISHandler.setFormatter(myFormatter)

    # add the handlers to the logger
    addLoggingHanderOnce(myLogger, myFileHandler)
    addLoggingHanderOnce(myLogger, myConsoleHandler)
    addLoggingHanderOnce(myLogger, myQGISHandler)


def getLayerAttributeNames(theLayer, theAllowedTypes, theCurrentKeyword=None):
    """iterates over self.layer and returns all the attribute names of
       attributes that have int or string as field type and the position
       of the theCurrentKeyword in the attribute names list

    Args:
       * theAllowedTypes: list(Qvariant) - a list of QVariants types that are
            acceptable for the attribute.
            e.g.: [QtCore.QVariant.Int, QtCore.QVariant.String]
       * theCurrentKeyword - the currently stored keyword for the attribute

    Returns:
       * all the attribute names of attributes that have int or string as
            field type
       * the position of the theCurrentKeyword in the attribute names list,
            this is None if theCurrentKeyword is not in the lis of attributes
    Raises:
       no exceptions explicitly raised
    """

    if theLayer.type() == QgsMapLayer.VectorLayer:
        myProvider = theLayer.dataProvider()
        myProvider = myProvider.fields()
        myFields = []
        mySelectedIndex = None
        i = 0
        for f in myProvider:
            # show only int or string myFields to be chosen as aggregation
            # attribute other possible would be float
            if myProvider[f].type() in theAllowedTypes:
                myCurrentFieldName = myProvider[f].name()
                myFields.append(myCurrentFieldName)
                if theCurrentKeyword == myCurrentFieldName:
                    mySelectedIndex = i
                i += 1
        return myFields, mySelectedIndex
    else:
        return None, None


def getDefaults(theDefault=None):
    """returns a dictionary of defaults values to be used
        it takes the DEFAULTS from safe and modifies them according to qgis
        QSettings

    Args:
       * theDefault: a key of the defaults dictionary

    Returns:
       * A dictionary of defaults values to be used
       * or the default value if a key is passed
       * or None if the requested default value is not valid
    Raises:
       no exceptions explicitly raised
    """
    mySettings = QtCore.QSettings()
    myDefaults = DEFAULTS

    myDefaults['FEM_RATIO'] = mySettings.value(
        'inasafe/defaultFemaleRatio',
        DEFAULTS['FEM_RATIO']).toDouble()[0]

    if theDefault is None:
        return myDefaults
    elif theDefault in myDefaults:
        return myDefaults[theDefault]
    else:
        return None


def copyInMemory(vLayer, copyName=''):
    """Return a memory copy of a layer

    Input
        origLayer: layer
        copyName: the name of the copy
    Output
        memory copy of a layer

    """

    if copyName is '':
        copyName = vLayer.name() + ' TMP'

    if vLayer.type() == QgsMapLayer.VectorLayer:
        vType = vLayer.geometryType()
        if vType == QGis.Point:
            typeStr = 'Point'
        elif vType == QGis.Line:
            typeStr = 'Line'
        elif vType == QGis.Polygon:
            typeStr = 'Polygon'
        else:
            raise MemoryLayerCreationError('Layer is whether Point nor '
                                           'Line nor Polygon')
    else:
        raise MemoryLayerCreationError('Layer is not a VectorLayer')

    crs = vLayer.crs().authid().toLower()
    myUUID = str(uuid.uuid4())
    uri = '%s?crs=%s&index=yes&uuid=%s' % (typeStr, crs, myUUID)
    memLayer = QgsVectorLayer(uri, copyName, 'memory')
    memProvider = memLayer.dataProvider()

    vProvider = vLayer.dataProvider()
    vAttrs = vProvider.attributeIndexes()
    vFields = vProvider.fields()

    fields = []
    for i in vFields:
        fields.append(vFields[i])

    memProvider.addAttributes(fields)

    vProvider.select(vAttrs)
    ft = QgsFeature()
    while vProvider.nextFeature(ft):
        memProvider.addFeatures([ft])

    if qgisVersion() <= 10800:
        # Next two lines a workaround for a QGIS bug (lte 1.8)
        # preventing mem layer attributes being saved to shp.
        memLayer.startEditing()
        memLayer.commitChanges()

    return memLayer


def mmToPoints(theMM, theDpi):
    """Convert measurement in points to one in mm.

    Args:
        * theMM: int - distance in millimeters
        * theDpi: int - dots per inch in the print / display medium
    Returns:
        mm converted value
    Raises:
        Any exceptions raised by the InaSAFE library will be propagated.
    """
    myInchAsMM = 25.4
    myPoints = (theMM * theDpi) / myInchAsMM
    return myPoints


def pointsToMM(thePoints, theDpi):
    """Convert measurement in points to one in mm.

    Args:
        * thePoints: int - number of points in display / print medium
        * theDpi: int - dots per inch in the print / display medium
    Returns:
        mm converted value
    Raises:
        Any exceptions raised by the InaSAFE library will be propagated.
    """
    myInchAsMM = 25.4
    myMM = (float(thePoints) / theDpi) * myInchAsMM
    return myMM


def dpiToMeters(theDpi):
    """Convert dots per inch (dpi) to dots perMeters.

    Args:
        theDpi: int - dots per inch in the print / display medium
    Returns:
        int - dpm converted value
    Raises:
        Any exceptions raised by the InaSAFE library will be propagated.
    """
    myInchAsMM = 25.4
    myInchesPerM = 1000.0 / myInchAsMM
    myDotsPerM = myInchesPerM * theDpi
    return myDotsPerM


def setupPrinter(theFilename,
                 theResolution=300,
                 thePageHeight=297,
                 thePageWidth=210):
    """Create a QPrinter instance defaulted to print to an A4 portrait pdf

    Args:
        theFilename - filename for pdf generated using this printer
    Returns:
        None
    Raises:
        None
    """
    #
    # Create a printer device (we are 'printing' to a pdf
    #
    LOGGER.debug('InaSAFE Map setupPrinter called')
    myPrinter = QtGui.QPrinter()
    myPrinter.setOutputFormat(QtGui.QPrinter.PdfFormat)
    myPrinter.setOutputFileName(theFilename)
    myPrinter.setPaperSize(
        QtCore.QSizeF(thePageWidth, thePageHeight),
        QtGui.QPrinter.Millimeter)
    myPrinter.setFullPage(True)
    myPrinter.setColorMode(QtGui.QPrinter.Color)
    myPrinter.setResolution(theResolution)
    return myPrinter


def humaniseSeconds(theSeconds):
    """Utility function to humanise seconds value into e.g. 10 seconds ago.

    The function will try to make a nice phrase of the seconds count
    provided.

    .. note:: Currently theSeconds that amount to days are not supported.

    Args:
        theSeconds: int - mandatory seconds value e.g. 1100

    Returns:
        str: A humanised version of the seconds count.

    Raises:
        None
    """
    myDays = theSeconds / (3600 * 24)
    myDayModulus = theSeconds % (3600 * 24)
    myHours = myDayModulus / 3600
    myHourModulus = myDayModulus % 3600
    myMinutes = myHourModulus / 60

    if theSeconds < 60:
        return tr('%i seconds' % theSeconds)
    if theSeconds < 120:
        return tr('a minute')
    if theSeconds < 3600:
        return tr('%s minutes' % myMinutes)
    if theSeconds < 7200:
        return tr('over an hour')
    if theSeconds < 86400:
        return tr('%i hours and %i minutes' % (myHours, myMinutes))
    else:
        # If all else fails...
        return tr('%i days, %i hours and %i minutes' % (
            myDays, myHours, myMinutes))


def impactLayerAttribution(theKeywords, theInaSAFEFlag=False):
    """Make a little table for attribution of data sources used in impact.

    Args:
        * theKeywords: dict{} - a keywords dict for an impact layer.
        * theInaSAFEFlag: bool - whether to show a little InaSAFE promotional
            text in the attribution output. Defaults to False.

    Returns:
        str: an html snippet containing attribution information for the impact
            layer. If no keywords are present or no appropriate keywords are
            present, None is returned.

    Raises:
        None
    """
    if theKeywords is None:
        return None
    myReport = ''
    myJoinWords = ' - %s ' % tr('sourced from')
    myHazardDetails = tr('Hazard details')
    myHazardTitleKeyword = 'hazard_title'
    myHazardSourceKeyword = 'hazard_source'
    myExposureDetails = tr('Exposure details')
    myExposureTitleKeyword = 'exposure_title'
    myExposureSourceKeyword = 'exposure_source'

    if myHazardTitleKeyword in theKeywords:
        # We use safe translation infrastructure for this one (rather than Qt)
        myHazardTitle = safeTr(theKeywords[myHazardTitleKeyword])
    else:
        myHazardTitle = tr('Hazard layer')

    if myHazardSourceKeyword in theKeywords:
        # We use safe translation infrastructure for this one (rather than Qt)
        myHazardSource = safeTr(theKeywords[myHazardSourceKeyword])
    else:
        myHazardSource = tr('an unknown source')

    if myExposureTitleKeyword in theKeywords:
        myExposureTitle = theKeywords[myExposureTitleKeyword]
    else:
        myExposureTitle = tr('Exposure layer')

    if myExposureSourceKeyword in theKeywords:
        myExposureSource = theKeywords[myExposureSourceKeyword]
    else:
        myExposureSource = tr('an unknown source')

    myReport += ('<table class="table table-striped condensed'
                 ' bordered-table">')
    myReport += '<tr><th>%s</th></tr>' % myHazardDetails
    myReport += '<tr><td>%s%s %s.</td></tr>' % (
        myHazardTitle,
        myJoinWords,
        myHazardSource)

    myReport += '<tr><th>%s</th></tr>' % myExposureDetails
    myReport += '<tr><td>%s%s %s.</td></tr>' % (
        myExposureTitle,
        myJoinWords,
        myExposureSource)

    if theInaSAFEFlag:
        myReport += '<tr><th>%s</th></tr>' % tr('Software notes')
        myInaSAFEPhrase = tr(
            'This report was created using InaSAFE '
            'version %1. Visit http://inasafe.org to get '
            'your free copy of this software!').arg(get_version())
        myInaSAFEPhrase += tr(
            'InaSAFE has been jointly developed by'
            ' BNPB, AusAid & the World Bank')
        myReport += '<tr><td>%s</td></tr>' % myInaSAFEPhrase

    myReport += '</table>'

    return myReport


def addComboItemInOrder(theCombo, theItemText, theItemData=None):
    """Although QComboBox allows you to set an InsertAlphabetically enum
    this only has effect when a user interactively adds combo items to
    an editable combo. This we have this little function to ensure that
    combos are always sorted alphabetically.

    Args:
        * theCombo - combo box receiving the new item
        * theItemText - display text for the combo
        * theItemData - optional UserRole data to be associated with
          the item

    Returns:
        None

    Raises:

    ..todo:: Move this to utilities
    """
    mySize = theCombo.count()
    for myCount in range(0, mySize):
        myItemText = str(theCombo.itemText(myCount))
        # see if theItemText alphabetically precedes myItemText
        if cmp(str(theItemText).lower(), myItemText.lower()) < 0:
            theCombo.insertItem(myCount, theItemText, theItemData)
            return
        #otherwise just add it to the end
    theCombo.insertItem(mySize, theItemText, theItemData)


def isPolygonLayer(theLayer):
    """Tell if a QGIS layer is vector and its geometries are polygons.

   Args:
       the theLayer

    Returns:
        bool - true if the theLayer contains polygons

    Raises:
       None
    """
    try:
        return (theLayer.type() == QgsMapLayer.VectorLayer) and (
            theLayer.geometryType() == QGis.Polygon)
    except AttributeError:
        return False


def isPointLayer(theLayer):
    """Tell if a QGIS layer is vector and its geometries are points.

   Args:
       the theLayer

    Returns:
        bool - true if the theLayer contains polygons

    Raises:
       None
    """
    try:
        return (theLayer.type() == QgsMapLayer.VectorLayer) and (
            theLayer.geometryType() == QGis.Point)
    except AttributeError:
        return False


def which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.

    ..note:: This function was taken verbatim from the twisted framework,
      licence available here:
      http://twistedmatrix.com/trac/browser/tags/releases/twisted-8.2.0/LICENSE

    On newer versions of MS-Windows, the PATHEXT environment variable will be
    set to the list of file extensions for files considered executable. This
    will normally include things like ".EXE". This fuction will also find files
    with the given name ending with any of these extensions.

    On MS-Windows the only flag that has any meaning is os.F_OK. Any other
    flags will be ignored.

    @type name: C{str}
    @param name: The name for which to search.

    @type flags: C{int}
    @param flags: Arguments to L{os.access}.

    @rtype: C{list}
    @param: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    #pylint: disable=W0141
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    #pylint: enable=W0141
    path = os.environ.get('PATH', None)
    # In c6c9b26 we removed this hard coding for issue #529 but I am
    # adding it back here in case the user's path does not include the
    # gdal binary dir on OSX but it is actually there. (TS)
    if sys.platform == 'darwin':  # Mac OS X
        myGdalPrefix = ('/Library/Frameworks/GDAL.framework/'
                        'Versions/1.9/Programs/')
        path = '%s:%s' % (path, myGdalPrefix)

    LOGGER.debug('Search path: %s' % path)

    if path is None:
        return []

    for p in path.split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)

    return result
