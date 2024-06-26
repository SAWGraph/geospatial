"""Create a .ttl file for a state's towns

Towns are defined based on census county subdivisions.
Under ### Input Filenames ###, define
    the name (and path) of the .shp file of county subdivisions
    the name (and path) of the .shp file of the state's S2 cells
Under ### Output Filename ###, define
    the name (and path) of the output .ttl file

Required:
    * geopandas
    * shapely (LineString, Point, and Polygon)
    * rdflib (Graph and Literal)
    * rdflib.namespace (GEO, RDF, RDFS, and XSD)
    * variable (a local .py file with a dictionary of project namespaces)

Functions:
    * initial_kg - initialize an RDFLib knowledge graph with project namespaces
    * build_iris - build IRIs for a given town and its geometries
    * find_s2_intersects_geom - find the S2 cells that are within or overlap a given town
    * main - parse all towns for a given state to the RDFLib graph
"""

import geopandas as gpd
from shapely import LineString, Point, Polygon
from rdflib import Graph, Literal
from rdflib.namespace import GEO, OWL, PROV, RDF, RDFS, XSD

import time
import datetime

import sys
import os

# Modify the system path to find variable.py
sys.path.insert(1, 'G:/My Drive/UMaine Docs from Laptop/SAWGraph/Data Sources')
from variable import _PREFIX, find_s2_intersects_geom

# Set the current directory to this file's directory
os.chdir('G:/My Drive/UMaine Docs from Laptop/SAWGraph/Data Sources/Administrative Regions')

### Input Filenames ###
# towns_file: a county subdivisions .shp file from the US Census Bureau
#    County subdivision shapefiles: https://www.census.gov/cgi-bin/geo/shapefiles/index.php
# s2_file: Level 13 S2 cells tat overlap/are within Maine
towns_file = '../Geospatial/tl_2023_23_cousub/tl_2023_23_cousub.shp'
s2_file = '../Geospatial/s2l13_23/s2l13_23.shp'

### Output Filename ###
# ttl_file: the resulting (output) .ttl file
ttl_file = 'me_towns.ttl'


def initial_kg(_PREFIX):
    """Create an empty knowledge graph with project namespaces

    :param _PREFIX: a dictionary of project namespaces
    :return: an RDFLib graph
    """
    graph = Graph()
    for prefix in _PREFIX:
        graph.bind(prefix, _PREFIX[prefix])
    return graph


def build_iris(gid):
    """Create IRIs for a town and its geometries

    :param gid: The 10-digit FIPS code for the town is expected as iinput (GEOID)
    :return: a tuple with the three IRIs
    """
    return (_PREFIX["dcgeoid"][gid],
            _PREFIX["sawgeo"]['d.Polygon.administrativeRegion.USA.' + gid],
            _PREFIX["sawgeo"]['d.Point.administrativeRegion.USA.' + gid])


def main():
    """Parse all towns (county subdivisions) within a state to an RDFLib knowledge graph

    Major components:
        * Read town and S2 cells .shp files to GeoDataFrames
        * Create an empty knowledge graph with project namespaces
        * Iterate through the towns
            * Create triples with the town as subject
            * Create triples with the point and polygon geometries as subjects
            * Create triples indicating which S2 cells are within or overlap the town

    :return: a complete knowledge graph
    """
    gdf_towns = gpd.read_file(towns_file)
    gdf_s2l13 = gpd.read_file(s2_file)
    graph = initial_kg(_PREFIX)
    count = 1
    n = len(gdf_towns.index)
    for row in gdf_towns.itertuples():
        name = row.NAMELSAD + ", Maine"
        towniri, polyiri, pntiri = build_iris(row.GEOID)

        graph.add((towniri, RDF.type, _PREFIX["kwg-ont"]['AdministrativeRegion_3']))
        graph.add((towniri, RDFS.label, Literal(name, datatype=XSD.string)))
        graph.add((towniri, _PREFIX["kwg-ont"]['administrativePartOf'],
                   _PREFIX["kwgr"]['administrativeRegion.USA.' + row.STATEFP + row.COUNTYFP]))
        graph.add((towniri, _PREFIX["kwg-ont"]['hasFIPS'], Literal(row.GEOID, datatype=XSD.string)))
        graph.add((towniri, _PREFIX["kwg-ont"]['sfWithin'],
                   _PREFIX["kwgr"]['administrativeRegion.USA.' + row.STATEFP + row.COUNTYFP]))
        graph.add((towniri, GEO.hasGeometry, polyiri))
        graph.add((towniri, GEO.hasGeometry, pntiri))
        graph.add((towniri, GEO['hasDefaultGeometry'], polyiri))

        graph.add((polyiri, RDF.type, GEO.Geometry))
        graph.add((polyiri, GEO.asWKT, Literal(row.geometry, datatype=GEO.wktLiteral)))
        graph.add((polyiri, RDFS.label, Literal('Polygon geometry of ' + name, datatype=XSD.string)))
        graph.add((pntiri, RDF.type, GEO.Geometry))
        graph.add((pntiri, GEO.asWKT,
                   Literal('POINT (' + row.INTPTLON.replace('-0', '-') + ' ' + row.INTPTLAT.replace('+', '') + ')',
                           datatype=GEO.wktLiteral)))
        graph.add((pntiri, RDFS.label, Literal('Point geometry of ' + name, datatype=XSD.string)))

        s2within, s2overlaps = find_s2_intersects_geom(row.geometry, gdf_s2l13)

        for s2 in s2within:
            graph.add((_PREFIX["kwgr"]['s2.level13.' + s2], _PREFIX["kwg-ont"]['sfWithin'], towniri))
        for s2 in s2overlaps:
            graph.add((_PREFIX["kwgr"]['s2.level13.' + s2], _PREFIX["kwg-ont"]['sfOverlaps'], towniri))

        print(f'Row {count:3} of {n} : {name:50}', end='\r', flush=True)
        count += 1
    print()
    return graph


if __name__ == "__main__":
    start_time = time.time()
    kg = main()
    kg.serialize(ttl_file, format='turtle')
    print(f'Runtime: {str(datetime.timedelta(seconds=time.time() - start_time))} HMS')
