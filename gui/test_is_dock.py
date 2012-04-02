"""
InaSAFE Disaster risk assessment tool developed by AusAid and World Bank
- **GUI Test Cases.**

Contact : ole.moller.nielsen@gmail.com

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'tim@linfiniti.com'
__version__ = '0.3.0'
__date__ = '10/01/2011'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')

import unittest
import sys
import os

# Add PARENT directory to path to make test aware of other modules
pardir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(pardir)

from PyQt4 import QtCore
from PyQt4.QtTest import QTest
from qgis.core import (QgsVectorLayer,
                       QgsRasterLayer,
                       QgsMapLayerRegistry)
from qgis.gui import QgsMapCanvasLayer
from utilities_test import (getQgisTestApp,
                            setCanvasCrs,
                            setPadangGeoExtent,
                            setBatemansBayGeoExtent,
                            setJakartaGeoExtent,
                            setYogyaGeoExtent,
                            setJakartaGoogleExtent,
                            setGeoExtent,
                            GEOCRS,
                            GOOGLECRS,
                            loadLayer)

from gui.is_dock import ISDock
from is_utilities import (setVectorStyle,
                          setRasterStyle)
from storage.utilities_test import TESTDATA
from storage.utilities import read_keywords

try:
    from pydevd import *
    print 'Remote debugging is enabled.'
    DEBUG = True
except Exception, e:
    print 'Debugging was disabled'

QGISAPP, CANVAS, IFACE, PARENT = getQgisTestApp()
DOCK = ISDock(IFACE)


def getUiState(ui):
    """Get state of the 3 combos on the DOCK ui. This method is purely for
    testing and not to be confused with the saveState and restoreState methods
    of inasafedock.
    """

    myHazard = str(ui.cboHazard.currentText())
    myExposure = str(ui.cboExposure.currentText())
    myImpactFunction = str(ui.cboFunction.currentText())

    myRunButton = ui.pbnRunStop.isEnabled()

    return {'Hazard': myHazard,
            'Exposure': myExposure,
            'Impact Function': myImpactFunction,
            'Run Button Enabled': myRunButton}


def formattedList(theList):
    """Return a string representing a list of layers (in correct order)
    but formatted with line breaks between each entry."""
    myListString = ''
    for myItem in theList:
        myListString += myItem + '\n'
    return myListString


def canvasList():
    """Return a string representing the list of canvas layers (in correct
    order) but formatted with line breaks between each entry."""
    myListString = ''
    for myLayer in CANVAS.layers():
        myListString += str(myLayer.name()) + '\n'
    return myListString


def combosToString(ui):
    """Helper to return a string showing the state of all combos (all their
    entries"""

    myString = 'Hazard Layers\n'
    myString += '-------------------------\n'
    myCurrentId = ui.cboHazard.currentIndex()
    for myCount in range(0, ui.cboHazard.count()):
        myItemText = ui.cboHazard.itemText(myCount)
        if myCount == myCurrentId:
            myString += '>> '
        else:
            myString += '   '
        myString += str(myItemText) + '\n'
    myString += '\n'
    myString += 'Exposure Layers\n'
    myString += '-------------------------\n'
    myCurrentId = ui.cboExposure.currentIndex()
    for myCount in range(0, ui.cboExposure.count()):
        myItemText = ui.cboExposure.itemText(myCount)
        if myCount == myCurrentId:
            myString += '>> '
        else:
            myString += '   '
        myString += str(myItemText) + '\n'

    myString += '\n'
    myString += 'Functions\n'
    myString += '-------------------------\n'
    myCurrentId = ui.cboExposure.currentIndex()
    for myCount in range(0, ui.cboFunction.count()):
        myItemText = ui.cboFunction.itemText(myCount)
        if myCount == myCurrentId:
            myString += '>> '
        else:
            myString += '   '
        myString += str(myItemText) + '\n'

    myString += '\n\n >> means combo item is selected'
    return myString


def populatemyDock():
    """A helper function to populate the DOCK and set it to a valid state.
    """
    loadStandardLayers()
    DOCK.cboHazard.setCurrentIndex(0)
    DOCK.cboExposure.setCurrentIndex(0)
    #QTest.mouseClick(myHazardItem, Qt.LeftButton)
    #QTest.mouseClick(myExposureItem, Qt.LeftButton)


def loadStandardLayers():
    """Helper function to load standard layers into the dialog."""
    # NOTE: Adding new layers here may break existing tests since
    # combos are populated alphabetically. Each test will
    # provide a detailed diagnostic if you break it so make sure
    # to consult that and clean up accordingly.
    myFileList = ['Padang_WGS84.shp',
                  'glp10ag.asc',
                  'Shakemap_Padang_2009.asc',
                  'tsunami_max_inundation_depth_BB_utm.asc',
                  'tsunami_exposure_BB.shp',
                  'Flood_Current_Depth_Jakarta_geographic.asc',
                  'Population_Jakarta_geographic.asc',
                  'eq_yogya_2006.asc',
                  'OSM_building_polygons_20110905.shp']
    myHazardLayerCount, myExposureLayerCount = loadLayers(myFileList)
    assert myHazardLayerCount + myExposureLayerCount == len(myFileList)
    return myHazardLayerCount, myExposureLayerCount


def loadLayers(theLayerList, theClearFlag=True):
    """Helper function to load layers as defined in a python list."""
    # First unload any layers that may already be loaded
    if theClearFlag:
        for myLayer in QgsMapLayerRegistry.instance().mapLayers():
            QgsMapLayerRegistry.instance().removeMapLayer(myLayer)

    # Now go ahead and load our layers
    myExposureLayerCount = 0
    myHazardLayerCount = 0
    myCanvasLayers = []

    # Now create our new layers
    for myFile in theLayerList:

        myLayer, myType = loadLayer(myFile)
        if myType == 'hazard':
            myHazardLayerCount += 1
        elif myType == 'exposure':
            myExposureLayerCount += 1
        # Add layer to the registry (that QGis knows about)
        QgsMapLayerRegistry.instance().addMapLayer(myLayer)

        # Create Map Canvas Layer Instance and add to list
        myCanvasLayers.append(QgsMapCanvasLayer(myLayer))

    # Quickly add any existing CANVAS layers to our list first
    for myLayer in CANVAS.layers():
        myCanvasLayers.append(QgsMapCanvasLayer(myLayer))
    # now load all these layers in the CANVAS
    CANVAS.setLayerSet(myCanvasLayers)
    DOCK.getLayers()

    # Add MCL's to the CANVAS
    return myHazardLayerCount, myExposureLayerCount


def loadLayer(theLayerFile):
    """Helper to load and return a single QGIS layer"""
    # Extract basename and absolute path
    myBaseName, myExt = os.path.splitext(theLayerFile)
    myPath = os.path.join(TESTDATA, theLayerFile)
    myKeywordPath = myPath[:-4] + '.keywords'
    # Determine if layer is hazard or exposure
    myKeywords = read_keywords(myKeywordPath)
    myType = 'undefined'
    if 'category' in myKeywords:
        myType = myKeywords['category']
    msg = 'Could not read %s' % myKeywordPath
    assert myKeywords is not None, msg

    # Create QGis Layer Instance
    if myExt in ['.asc', '.tif']:
        myLayer = QgsRasterLayer(myPath, myBaseName)
    elif myExt in ['.shp']:
        myLayer = QgsVectorLayer(myPath, myBaseName, 'ogr')
    else:
        myMessage = 'File %s had illegal extension' % myPath
        raise Exception(myMessage)

    myMessage = 'Layer "%s" is not valid' % str(myLayer.source())
    assert myLayer.isValid(), myMessage
    return myLayer, myType


class ISDockTest(unittest.TestCase):
    """Test the InaSAFE GUI"""

    def setUp(self):
        """Fixture run before all tests"""
        DOCK.showOnlyVisibleLayersFlag = True
        DOCK.bubbleLayersUpFlag = False
        loadStandardLayers()
        DOCK.cboHazard.setCurrentIndex(0)
        DOCK.cboExposure.setCurrentIndex(0)
        DOCK.cboFunction.setCurrentIndex(0)

    def tearDown(self):
        """Fixture run after each test"""
        QgsMapLayerRegistry.instance().removeAllMapLayers()
        DOCK.cboHazard.clear()
        DOCK.cboExposure.clear()

    def test_defaults(self):
        """Test the GUI in its default state"""
        self.assertEqual(DOCK.cboHazard.currentIndex(), 0)
        self.assertEqual(DOCK.cboExposure.currentIndex(), 0)
        self.assertEqual(DOCK.cboFunction.currentIndex(), 0)

    def test_validate(self):
        """Validate function work as expected"""
        self.tearDown()
        # First check that we DONT validate a clear DOCK
        myFlag, myMessage = DOCK.validate()
        assert myMessage is not None, 'No reason for failure given'

        myMessage = 'Validation expected to fail on a cleared DOCK.'
        self.assertEquals(myFlag, False, myMessage)

        # Now check we DO validate a populated DOCK
        populatemyDock()
        myFlag = DOCK.validate()
        myMessage = ('Validation expected to pass on '
                     'a populated for with selections.')
        assert myFlag, myMessage

    def test_setOkButtonStatus(self):
        """OK button changes properly according to DOCK validity"""
        # First check that we ok ISNT enabled on a clear DOCK
        self.tearDown()
        myFlag, myMessage = DOCK.validate()

        assert myMessage is not None, 'No reason for failure given'
        myMessage = 'Validation expected to fail on a cleared DOCK.'
        self.assertEquals(myFlag, False, myMessage)

        # Now check OK IS enabled on a populated DOCK
        populatemyDock()
        myFlag = DOCK.validate()
        myMessage = ('Validation expected to pass on a ' +
                     'populated DOCK with selections.')
        assert myFlag, myMessage

    def test_runEarthQuakeGuidelinesFunction(self):
        """GUI runs with Shakemap 2009 and Padang Buildings"""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop
        setCanvasCrs(GEOCRS, True)
        setPadangGeoExtent()
        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)

        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        myDict = getUiState(DOCK)
        myExpectedDict = {'Hazard': 'Shakemap_Padang_2009',
                        'Exposure': 'Padang_WGS84',
                        'Impact Function': 'Earthquake Guidelines Function',
                        'Run Button Enabled': True}
        myMessage = 'Got:\n %s\nExpected:\n%s\n%s' % (
                        myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()
        # Expected output:
        #Buildings    Total
        #All:    3160
        #Low damage (10-25%):    0
        #Medium damage (25-50%):    0
        #Pre merge of clip on steroids branch:
        #High damage (50-100%):    3160
        # Post merge of clip on steoids branch:
        #High damage (50-100%):    2993
        myMessage = ('Unexpected result returned for Earthquake guidelines'
               'function. Expected:\n "All" count of 2993, '
               'received: \n %s' % myResult)
        assert '2993' in myResult, myMessage

    def test_runEarthquakeFatalityFunction_small(self):
        """Padang 2009 fatalities estimated correctly - small extent"""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop
        setCanvasCrs(GEOCRS, True)
        setPadangGeoExtent()

        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # Simulate choosing another combo item and running
        # the model again
        # set hazard to Shakemap_Padang_2009
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)
        # set exposure to Population Density Estimate (5kmx5km)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        myDict = getUiState(DOCK)
        myExpectedDict = {'Hazard': 'Shakemap_Padang_2009',
                        'Exposure': 'Population Density Estimate (5kmx5km)',
                        'Impact Function': 'Earthquake Fatality Function',
                        'Run Button Enabled': True}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)

        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        # Check against expected output
        myMessage = ('Unexpected result returned for Earthquake Fatality '
                     'Function Expected: fatality count of '
                     '116 , received: \n %s' % myResult)
        assert '116' in myResult, myMessage

        myMessage = ('Unexpected result returned for Earthquake Fatality '
                     'Function Expected: total population count of '
                     '847529 , received: \n %s' % myResult)
        assert '847529' in myResult, myMessage

    def test_runEarthquakeFatalityFunction_Padang_full(self):
        """Padang 2009 fatalities estimated correctly"""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop
        setCanvasCrs(GEOCRS, True)
        setGeoExtent([96, -5, 105, 2])  # This covers all of the 2009 shaking
        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # set hazard to Shakemap_Padang_2009
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)
        # Simulate choosing another combo item and running
        # the model again - Population Density Estimate (5kmx5km)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        myDict = getUiState(DOCK)
        myExpectedDict = {'Hazard': 'Shakemap_Padang_2009',
                      'Exposure': 'Population Density Estimate (5kmx5km)',
                      'Impact Function': 'Earthquake Fatality Function',
                      'Run Button Enabled': True}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)

        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        # Check against expected output
        myMessage = ('Unexpected result returned for Earthquake Fatality '
                     'Function Expected: fatality count of '
                     '500 , received: \n %s' % myResult)
        assert '500' in myResult, myMessage

        myMessage = ('Unexpected result returned for Earthquake Fatality '
                     'Function Expected: total population count of '
                     '31372262 , received: \n %s' % myResult)
        assert '31372262' in myResult, myMessage

    def test_runTsunamiBuildingImpactFunction(self):
        """Tsunami function runs in GUI with Batemans Bay model"""
        """Raster and vector based function runs as expected."""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop

        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # Hazard layers
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)

        # Exposure layers
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        # Check that layers and impact function are correct
        myDict = getUiState(DOCK)

        myExpectedDict = {'Run Button Enabled': True,
                        'Impact Function': 'Tsunami Building Impact Function',
                        'Hazard': 'tsunami_max_inundation_depth_BB_utm',
                        'Exposure': 'tsunami_exposure_BB'}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        setCanvasCrs(GEOCRS, True)
        setBatemansBayGeoExtent()

        # Press RUN
        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        #print myResult
        # Post clip on steroids refactor
        # < 1 m:    1923
        # 1 - 3 m:    89
        # > 3 m:    0
        myMessage = 'Result not as expected: %s' % myResult
        assert '1923' in myResult, myMessage
        assert '89' in myResult, myMessage
        assert '0' in myResult, myMessage

    def test_runFloodPopulationImpactFunction(self):
        """Flood function runs in GUI with Jakarta data
           Raster on raster based function runs as expected."""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop

        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # Hazard layers - default is already Banjir Jakarta seperti 2007

        # Exposure layers - Penduduk Jakarta
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        # Choose impact Terdampak
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)

        # Check that layers and impact function are correct
        myDict = getUiState(DOCK)

        myExpectedDict = {'Run Button Enabled': True,
                        'Impact Function': 'Terdampak',
                        'Hazard': 'Banjir Jakarta seperti 2007',
                        'Exposure': 'Penduduk Jakarta'}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        # Enable on-the-fly reprojection
        setCanvasCrs(GEOCRS, True)
        setJakartaGeoExtent()

        # Press RUN
        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        #Apabila terjadi "Flood Depth (current) Jakarta"
        # perkiraan dampak terhadap "clip_CCaFFQ" kemungkinan yang terjadi:
        #Terdampak (x 1000):    1

        # Pre clipping fix scores:

        #Catatan:
        #- Jumlah penduduk Jakarta 2 <-- should be about 8000
        #- Jumlah dalam ribuan
        #- Penduduk dianggap terdampak ketika banjir
        #lebih dari 0.1 m.  <-- expecting around 2400
        #Terdampak (x 1000): 2479

        # Post clipping fix scores

        #Catatan:
        #- Jumlah penduduk Jakarta 356018
        #- Jumlah dalam ribuan
        #- Penduduk dianggap terdampak ketika banjir lebih dari 0.1 m.
        #print myResult

        msg = 'Result not as expected: %s' % myResult
        assert '2480' in myResult, msg  # This is the expected impact number

    def test_runFloodPopulationImpactFunction_scaling(self):
        """Flood function runs in GUI with 5x5km population data
           Raster on raster based function runs as expected with scaling."""

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop

        msg = 'Run button was not enabled'
        assert myButton.isEnabled(), msg

        # Hazard layers use default - Banjir Jakarta seperti 2007

        # Exposure layers - Population Density Estimate (5kmx5km)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        # Choose impact function Terdampak
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)

        # Check that layers and impact function are correct
        myDict = getUiState(DOCK)

        myExpectedDict = {'Run Button Enabled': True,
                        'Impact Function': 'Terdampak',
                        'Hazard': 'Banjir Jakarta seperti 2007',
                        'Exposure': 'Population Density Estimate (5kmx5km)'}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        # Enable on-the-fly reprojection
        setCanvasCrs(GEOCRS, True)
        setJakartaGeoExtent()

        # Press RUN
        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        msg = 'Result not as expected: %s' % myResult

        # Check numbers are OK (within expected errors from resampling)
        assert '10484' in myResult, msg
        assert '2312' in myResult, msg  # These are expected impact number

    def test_ResultStyling(self):
        """Test that ouputs from a model are correctly styled (colours and
        opacity. """

        # Push OK with the left mouse button

        myButton = DOCK.pbnRunStop

        msg = 'Run button was not enabled'
        assert myButton.isEnabled(), msg

        # Hazard layers -already set to correct entry
        # Exposure layers - set to Penduduk Jakarta
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        # Choose impact function (second item in the list)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)
        myFunction = DOCK.cboFunction.currentText()
        myMessage = ('Incorrect function selected - expected Terdampak,'
                     ' got %s \n%s'
                     % (myFunction, combosToString(DOCK)))
        assert myFunction == 'Terdampak', myMessage

        # Enable on-the-fly reprojection
        setCanvasCrs(GEOCRS, True)
        setJakartaGeoExtent()

        # Run manually so we can get the output layer
        DOCK.setupCalculator()
        myRunner = DOCK.calculator.getRunner()
        myRunner.run()  # Run in same thread
        myEngineImpactLayer = myRunner.impactLayer()
        myQgisImpactLayer = DOCK.readImpactLayer(myEngineImpactLayer)
        myStyle = myEngineImpactLayer.get_style_info()
        #print myStyle
        setRasterStyle(myQgisImpactLayer, myStyle)
        # simple test for now - we could test explicity for style state
        # later if needed.
        myMessage = ('Raster layer was not assigned a ColorRampShader'
                     ' as expected.')
        assert myQgisImpactLayer.colorShadingAlgorithm() == \
                QgsRasterLayer.ColorRampShader, myMessage

        myMessage = ('Raster layer was not assigned transparency'
                     'classes as expected.')
        myTransparencyList = (myQgisImpactLayer.rasterTransparency().
                transparentSingleValuePixelList())
        #print "Transparency list:" + str(myTransparencyList)
        assert (len(myTransparencyList) > 0)

    def test_Issue47(self):
        """Issue47: Problem when hazard & exposure data are in different
        proj to viewport.
        See https://github.com/AIFDR/inasafe/issues/47"""

        myButton = DOCK.pbnRunStop
        myDict = getUiState(DOCK)
        myMessage = 'Run button was not enabled - UI State: %s\n%s' % (
                        myDict, combosToString(DOCK))
        assert myButton.isEnabled(), myMessage

        # Hazard layers - already on correct entry
        # Exposure layers
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        # Choose impact function (second item in the list)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)

        # Check that layers and impact function are correct
        myDict = getUiState(DOCK)
        myExpectedDict = {'Run Button Enabled': True,
                        'Impact Function': 'Terdampak',
                        'Hazard': 'Banjir Jakarta seperti 2007',
                        'Exposure': 'Penduduk Jakarta'}
        myMessage = 'Got: %s\nExpected: %s \n%s' % (
                        myDict, str(myExpectedDict), combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        # Enable on-the-fly reprojection
        setCanvasCrs(GOOGLECRS, True)
        setJakartaGoogleExtent()

        # Press RUN
        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        myMessage = 'Result not as expected: %s' % myResult
        #Terdampak (x 1000):    2366
        assert '2366' in myResult, myMessage

    def test_issue45(self):
        """Points near the edge of a raster hazard layer are interpolated OK"""

        myButton = DOCK.pbnRunStop
        setCanvasCrs(GEOCRS, True)
        setYogyaGeoExtent()

        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # Hazard layers  -Yogya2006
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)
        # Exposure layers - OSM Building Polygons
        # Choose impact function
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)

        # Check that layers and impact function are correct
        myDict = getUiState(DOCK)
        myExpectedDict = {'Hazard': 'Yogya2006',
                      'Exposure': 'OSM Building Polygons',
                      'Impact Function': 'Earthquake Guidelines Function',
                      'Run Button Enabled': True}
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myDict == myExpectedDict, myMessage

        # This is the where nosetest sometims hangs when running the
        # guitest suite (Issue #103)
        # The QTest.mouseClick call some times never returns when run
        # with nosetest, but OK when run normally.
        QTest.mouseClick(myButton, QtCore.Qt.LeftButton)
        myResult = DOCK.wvResults.page().currentFrame().toPlainText()

        # Check that none of these  get a NaN value:
        assert 'Unknown' in myResult

        myMessage = ('Some buildings returned by Earthquake guidelines '
                     'function '
                     'had NaN values. Result: \n %s' % myResult)
        assert 'Unknown (NaN):	196' not in myResult, myMessage

        # FIXME (Ole): A more robust test would be to load the
        #              result layer and check that all buildings
        #              have values.
        #              Tim, how do we get the output filename?
        # ANSWER
        #DOCK.calculator.impactLayer()

    def test_loadLayers(self):
        """Layers can be loaded and list widget was updated appropriately
        """

        myHazardLayerCount, myExposureLayerCount = loadStandardLayers()
        myMessage = 'Expect %s layer(s) in hazard list widget but got %s' \
                     % (myHazardLayerCount, DOCK.cboHazard.count())
        self.assertEqual(DOCK.cboHazard.count(),
                         myHazardLayerCount), myMessage

        myMessage = 'Expect %s layer(s) in exposure list widget but got %s' \
              % (myExposureLayerCount, DOCK.cboExposure.count())
        self.assertEqual(DOCK.cboExposure.count(),
                         myExposureLayerCount), myMessage

    def test_Issue71(self):
        """Test issue #71 in githib - cbo changes should update ok button."""
        # See https://github.com/AIFDR/inasafe/issues/71
        # Push OK with the left mouse button
        self.tearDown()
        myButton = DOCK.pbnRunStop
        # First part of scenario should have enabled run
        myFileList = ['Flood_Current_Depth_Jakarta_geographic.asc',
                      'Population_Jakarta_geographic.asc']
        myHazardLayerCount, myExposureLayerCount = loadLayers(myFileList)

        myMessage = ("Incorrect number of Hazard layers: expected 1 got %s"
                     % myHazardLayerCount)
        assert myHazardLayerCount == 1, myMessage

        myMessage = ("Incorrect number of Exposure layers: expected 1 got %s"
                     % myExposureLayerCount)
        assert myExposureLayerCount == 1, myMessage
        myMessage = 'Run button was not enabled'
        assert myButton.isEnabled(), myMessage

        # Second part of scenario - run disables when adding invalid layer
        # and select it - run should be disabled
        myFileList = ['issue71.tif']  # This layer has incorrect keywords
        myClearFlag = False
        myHazardLayerCount, myExposureLayerCount = (
            loadLayers(myFileList, myClearFlag))
        # set exposure to : Population Density Estimate (5kmx5km)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)
        myDict = getUiState(DOCK)
        myExpectedDict = {'Run Button Enabled': False,
                          'Impact Function': '',
                          'Hazard': 'Banjir Jakarta seperti 2007',
                          'Exposure': 'Population Density Estimate (5kmx5km)'}
        myMessage = ('Run button was not disabled when exposure set to \n%s'
                     '\nUI State: \n%s\nExpected State:\n%s\n%s') % (
                        DOCK.cboExposure.currentText(),
                        myDict,
                        myExpectedDict,
                        combosToString(DOCK)
                        )

        assert myExpectedDict == myDict, myMessage

        # Now select again a valid layer and the run button
        # should be enabled
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Up)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)
        myMessage = 'Run button was not enabled when exposure set to \n%s' % \
            DOCK.cboExposure.currentText()
        assert myButton.isEnabled(), myMessage

    def test_state(self):
        """Check if the save/restart state methods work. See also
        https://github.com/AIFDR/inasafe/issues/58
        """

        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Up)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)
        DOCK.saveState()
        myExpectedDict = getUiState(DOCK)
        #myState = DOCK.state
        # Now reset and restore and check that it gets the old state
        # Html is not considered in restore test since the ready
        # message overwrites it in dock implementation
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Up)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)
        DOCK.restoreState()
        myResultDict = getUiState(DOCK)
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myResultDict, myExpectedDict, combosToString(DOCK))
        assert myExpectedDict == myResultDict, myMessage

        # corner case test when two layers can have the
        # same functions
        self.tearDown()
        myFileList = ['Flood_Design_Depth_Jakarta_geographic.asc',
                      'Flood_Current_Depth_Jakarta_geographic.asc',
                      'Population_Jakarta_geographic.asc']
        myHazardLayerCount, myExposureLayerCount = loadLayers(myFileList)
        assert myHazardLayerCount == 2
        assert myExposureLayerCount == 1
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboFunction, QtCore.Qt.Key_Enter)
        # will need to udpate this when localisation is set up nicely
        myExpectedDict = {'Run Button Enabled': True,
                          'Impact Function': 'Terdampak',
                          'Hazard': 'Banjir Jakarta seperti 2007',
                          'Exposure': 'Penduduk Jakarta'}
        myDict = getUiState(DOCK)
        myMessage = 'Got unexpected state: %s\nExpected: %s\n%s' % (
                            myDict, myExpectedDict, combosToString(DOCK))
        assert myExpectedDict == myDict, myMessage
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Down)
        QTest.keyClick(DOCK.cboHazard, QtCore.Qt.Key_Enter)
        # selected function should remain the same
        myExpectation = 'Terdampak'
        myFunction = DOCK.cboFunction.currentText()
        myMessage = 'Expected: %s, Got: %s' % (myExpectation, myFunction)
        assert myFunction == myExpectation, myMessage

    def test_layerChanged(self):
        """Test the metadata is updated as the user highlights different
        QGIS layers. For inasafe outputs, the table of results should be shown
        See also
        https://github.com/AIFDR/inasafe/issues/58
        """
        myLayer, myType = loadLayer('issue58.tif')
        myMessage = ('Unexpected category for issue58.tif.\nGot:'
                     ' %s\nExpected: undefined' % myType)

        assert myType == 'undefined', myMessage
        DOCK.layerChanged(myLayer)
        DOCK.saveState()
        myHtml = DOCK.state['report']
        myExpectedString = '4229'
        myMessage = "%s\nDoes not contain:\n%s" % (
                                myHtml,
                                myExpectedString)
        assert myExpectedString in myHtml, myMessage

    def test_bubbleLayers(self):
        """Test the bubbleLayers method works
        """
        self.tearDown()
        # First part of scenario should have enabled run
        myFileList = ['Flood_Design_Depth_Jakarta_geographic.asc',
                      'Flood_Current_Depth_Jakarta_geographic.asc',
                      'Population_Jakarta_geographic.asc']
        loadLayers(myFileList)
        DOCK.bubbleLayersUpFlag = True
        DOCK.bubbleLayers()
        myExpectedList = ['Penduduk Jakarta',
                          'Banjir Jakarta seperti 2007',
                          'Banjir Jakarta Mungkin']
        myExpectedString = formattedList(myExpectedList)
        myCanvasListString = canvasList()
        myMessage = '\nGot Canvas Layer Order: \n%s\nExpected:\n%s\n\n%s' % (
                            myCanvasListString, myExpectedString,
                            combosToString(DOCK))
        assert myExpectedString == myCanvasListString, myMessage

        # Now select a differnt hazard and check the layers have bubbled
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Up)
        QTest.keyClick(DOCK.cboExposure, QtCore.Qt.Key_Enter)

        myExpectedList = ['Penduduk Jakarta',
                          'Banjir Jakarta Mungkin',
                          'Banjir Jakarta seperti 2007']
        myExpectedString = formattedList(myExpectedList)
        myCanvasListString = canvasList()
        myMessage = '\nGot Canvas Layer Order: \n%s\nExpected:\n%s\n\n%s' % (
                            myCanvasListString, myExpectedString,
                            combosToString(DOCK))

if __name__ == '__main__':
    suite = unittest.makeSuite(ISDockTest, 'test')
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
