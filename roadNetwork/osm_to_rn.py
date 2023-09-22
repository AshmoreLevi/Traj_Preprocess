import os
import networkx as nx
import osmium as o
from osgeo import ogr
import argparse
from const import candi_highway_types


class OSM2RNHandler(o.SimpleHandler):

    def __init__(self, rn):
        super(OSM2RNHandler, self).__init__()
        self.candi_highway_types = candi_highway_types
        self.rn = rn
        self.eid = 0

    def way(self, w):
        if 'highway' in w.tags and w.tags['highway'] in self.candi_highway_types:
            raw_eid = w.id
            full_coords = []

            for n in w.nodes:
                try:
                    # 检查节点的位置信息是否有效
                    if n.location.valid():
                        full_coords.append((n.lat, n.lon))
                    else:
                        print(f"跳过无效的位置信息：节点 {n.ref}")
                except o.InvalidLocationError:
                    print(f"无效的位置信息：节点 {n.ref}")
            
            if len(full_coords) < 2:
                # 如果路径中有效节点数少于2，跳过处理
                print("路径包含少于2个有效节点，跳过处理")
                return


            if 'oneway' in w.tags:
                if w.tags['oneway'] != 'yes':
                    full_coords.reverse()
                for i in range(len(full_coords)-1):
                    coords = [full_coords[i], full_coords[i + 1]]
                    edge_attr = {'eid': self.eid, 'coords': coords, 'raw_eid': raw_eid, 'highway': w.tags['highway']}
                    rn.add_edge(coords[0], coords[-1], **edge_attr)
                    self.eid += 1
            else:
                for i in range(len(full_coords)-1):
                    coords = [full_coords[i], full_coords[i + 1]]
                    # add edges for both directions
                    edge_attr = {'eid': self.eid, 'coords': coords, 'raw_eid': raw_eid, 'highway': w.tags['highway']}
                    rn.add_edge(coords[0], coords[-1], **edge_attr)
                    self.eid += 1

                reversed_full_coords = full_coords.copy()
                reversed_full_coords.reverse()
                for i in range(len(reversed_full_coords)-1):
                    reversed_coords = [full_coords[i], full_coords[i + 1]]
                    edge_attr = {'eid': self.eid, 'coords': reversed_coords, 'raw_eid': raw_eid, 'highway': w.tags['highway']}
                    rn.add_edge(reversed_coords[0], reversed_coords[-1], **edge_attr)
                    self.eid += 1


def store_shp(rn, target_path):
    ''' nodes: [lng, lat] '''
    rn.remove_nodes_from(list(nx.isolates(rn)))
    print('# of nodes:{}'.format(rn.number_of_nodes()))
    print('# of edges:{}'.format(rn.number_of_edges()))
    for _, _, data in rn.edges(data=True):
        geo_line = ogr.Geometry(ogr.wkbLineString)
        for coord in data['coords']:
            geo_line.AddPoint(coord[0], coord[1])
        data['Wkb'] = geo_line.ExportToWkb()
        del data['coords']
    nx.write_shp(rn, target_path)

def store_osm(rn, target_path):
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    """nodes: [lat, lng]"""
    print('# of nodes:{}'.format(rn.number_of_nodes()))
    print('# of edges:{}'.format(rn.number_of_edges()))
    node_map = {k: idx for idx, k in enumerate(rn.nodes())}

    with open(os.path.join(target_path, 'nodeOSM.txt'), 'w+') as node:
        for idx, coord in enumerate(rn.nodes()):
            node.write(f'{"%-6d"%idx} {coord[0]} {coord[1]}\n')
        node.close()

    edges = {}
    for stcoord, encoord, data in rn.edges(data=True):
        edges[data['eid']] = {'st': node_map[stcoord],
                              'en': node_map[encoord],
                              'coords': data["coords"],
                              'type': data['highway']}

    with open(os.path.join(target_path, 'edgeOSM.txt'), 'w+') as edge:
        for idx, k in enumerate(sorted(edges.keys())):
            edge.write(f'{idx} {edges[k]["st"]} {edges[k]["en"]} {len(edges[k]["coords"])}')
            for coord in edges[k]["coords"]:
                edge.write(f' {coord[0]} {coord[1]}')
            edge.write('\n')
        edge.close()

    with open(os.path.join(target_path, 'wayTypeOSM.txt'), 'w+') as waytype:
        for idx, k in enumerate(sorted(edges.keys())):
            waytype.write(f'{"%-6d"%idx} {"%-10s"%edges[k]["type"]} {"%-4d"%candi_highway_types[edges[k]["type"]]}\n')
        waytype.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_path', default='clipped_beijing.osm.pbf', help='the input path of the original osm data')
    parser.add_argument('--output_path', default='beijingRN_OSM', help='the output directory of the constructed road network')
    opt = parser.parse_args()
    print(opt)

    rn = nx.DiGraph()
    handler = OSM2RNHandler(rn)
    handler.apply_file(opt.input_path, locations=True)
    store_osm(rn, opt.output_path)
