bl_info = {
    "name": "Painter Effect",
    "blender": (2, 80, 0),
    "category": "Object",
}

import collections
import bpy
import bmesh


class ObjectPainterEffect(bpy.types.Operator):
    """Object Cursor Array"""
    bl_idname = "object.painter_effect"
    bl_label = "Painter Effect"
    bl_options = {'REGISTER', 'UNDO'}
    node_x_location = 0


    def create_node(self, node_tree, type_name, node_location_step_x=300):
        node_obj = node_tree.nodes.new(type=type_name)
        node_obj.location.x = self.node_x_location
        self.node_x_location += node_location_step_x

        return node_obj

    def execute(self, context):
        obj = context.active_object
        curves = self.generate_surface_curves(obj, context)
        self.create_tangent_tracer_group(obj, curves)
    
        self.create_geometry_nodes(obj)
        self.create_shader(obj)

        return {'FINISHED'}
    
    def create_geometry_nodes(self, obj):
            
        node_tree = None

        # Check if the object has a geometry nodes modifier
        if obj.modifiers and obj.modifiers.get("GeometryNodes"):
            print("get existing")
            # Get the geometry nodes modifier
            modifier = obj.modifiers["GeometryNodes"]

            # Access the node tree
            node_tree = modifier.node_group
        else:
            print("creating new")
            modifier = obj.modifiers.new(name="GeometryNodes", type='NODES')

            node_tree = bpy.data.node_groups.new('painter_geometry_node', 'GeometryNodeTree')
            # Get the node tree
            modifier.node_group = node_tree

        node_tree.nodes.clear()

#        size_x_socket = node_tree.interface.new_socket(name='Size X', socket_type='NodeSocketFloat')
#        size_y_socket = node_tree.interface.new_socket(name='Size Y', socket_type='NodeSocketFloat')
#        density_socket = node_tree.interface.new_socket(name='Density', socket_type='NodeSocketFloat')
#        rotate_socket = node_tree.interface.new_socket(name='Rotate By', socket_type='NodeSocketVector')
#        material_socket = node_tree.interface.new_socket(name='Material', socket_type='NodeSocketMaterial')
        
        group_input = self.create_node(node_tree, 'NodeGroupInput')
        group_input.location = (0, 0)
        
        distributePoint = self.create_node(node_tree, "GeometryNodeDistributePointsOnFaces")
        distributePoint.inputs[4].default_value = 31.700
        distributePoint.location = (200, 200)
        
        alignNormal = self.create_node(node_tree, "FunctionNodeAlignRotationToVector")
        alignNormal.location = (400, 100)
        
        grid = self.create_node(node_tree, "GeometryNodeMeshGrid")
        grid.location = (200, -100)
        
        store_uv_map = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_uv_map.inputs["Name"].default_value = "UVMap" 
        store_uv_map.data_type = 'FLOAT_VECTOR'
        store_uv_map.domain = "POINT" 
        store_uv_map.location = (400, -100)
        
        instanceOnPoint = self.create_node(node_tree, "GeometryNodeInstanceOnPoints")
        instanceOnPoint.inputs["Scale"].default_value = (0.5, 0.3, 0.02)
        instanceOnPoint.location = (600, 200)
        
        translateBrush = self.create_node(node_tree, "GeometryNodeTranslateInstances")
        translateBrush.location = (800, 200)
        translateBrush.inputs['Translation'].default_value[2] = 0.02
        
        store_normal = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_normal.inputs["Name"].default_value = "normal" 
        store_normal.data_type = 'FLOAT_VECTOR'
        store_normal.domain = "INSTANCE" 
        store_normal.location = (1000, 0)
        
        random_value = self.create_node(node_tree, "FunctionNodeRandomValue")
        random_value.data_type = 'FLOAT_VECTOR'
        random_value.inputs['Min'].default_value = (-1.0, -1.0, -1.0) 
        random_value.inputs['Max'].default_value = (1.0, 1.0, 1.0) 
        random_value.location = (1000, 400)
        
        store_random = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_random.inputs["Name"].default_value = "random" 
        store_random.data_type = 'FLOAT_VECTOR'
        store_random.domain = "INSTANCE" 
        store_random.location = (1200, 0)
        
        joinGeometry = self.create_node(node_tree, "GeometryNodeJoinGeometry")
        joinGeometry.location = (1400, 0)
        
        set_material = self.create_node(node_tree, "GeometryNodeSetMaterial")
        set_material.location = (1600, 0)
        
#        group_input_material = self.create_node(node_tree, "NodeGroupInput")
#        group_input_material.location = (1200, -200)
        
        self_object = self.create_node(node_tree, 'GeometryNodeSelfObject')
        self_object.location = (200, 500)
        
        object_info = self.create_node(node_tree, 'GeometryNodeObjectInfo')
        object_info.transform_space = 'ORIGINAL'
        object_info.location = (400, 500)
        
        vector_rotate = self.create_node(node_tree, "ShaderNodeVectorRotate")
        vector_rotate.rotation_type = 'EULER_XYZ' 
        vector_rotate.location = (600, 500)
        
        group_output = self.create_node(node_tree, 'NodeGroupOutput')
        group_output.location = (1800, 0)
        node_tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        node_tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        
        node_tree.links.new(group_input.outputs["Geometry"], distributePoint.inputs["Mesh"])
#        node_tree.links.new(group_input.outputs["Size X"], grid.inputs["Size X"])
#        node_tree.links.new(group_input.outputs["Size Y"], grid.inputs["Size Y"])
        node_tree.links.new(distributePoint.outputs["Points"], instanceOnPoint.inputs["Points"])
        node_tree.links.new(distributePoint.outputs["Normal"], alignNormal.inputs["Vector"])
        node_tree.links.new(alignNormal.outputs["Rotation"], instanceOnPoint.inputs["Rotation"])
        node_tree.links.new(grid.outputs["Mesh"], store_uv_map.inputs["Geometry"])
        node_tree.links.new(grid.outputs["UV Map"], store_uv_map.inputs["Value"])
        node_tree.links.new(distributePoint.outputs["Points"], instanceOnPoint.inputs["Points"])
        node_tree.links.new(store_uv_map.outputs["Geometry"], instanceOnPoint.inputs["Instance"])
        node_tree.links.new(instanceOnPoint.outputs["Instances"], translateBrush.inputs["Instances"])
        node_tree.links.new(translateBrush.outputs["Instances"], store_normal.inputs["Geometry"])
        node_tree.links.new(random_value.outputs["Value"], store_random.inputs["Value"])
        node_tree.links.new(store_normal.outputs["Geometry"], store_random.inputs["Geometry"])
        node_tree.links.new(store_random.outputs["Geometry"], joinGeometry.inputs["Geometry"])
        node_tree.links.new(group_input.outputs["Geometry"], joinGeometry.inputs["Geometry"])
        node_tree.links.new(joinGeometry.outputs["Geometry"], set_material.inputs["Geometry"])
#        node_tree.links.new(group_input.outputs["Material"], set_material.inputs["Material"])
        node_tree.links.new(self_object.outputs["Self Object"], object_info.inputs["Object"])
        node_tree.links.new(object_info.outputs["Rotation"], vector_rotate.inputs["Rotation"])
        node_tree.links.new(distributePoint.outputs["Normal"], vector_rotate.inputs["Vector"])
        node_tree.links.new(vector_rotate.outputs["Vector"], store_normal.inputs["Value"])
        node_tree.links.new(set_material.outputs["Geometry"], group_output.inputs["Geometry"])

    def create_shader(self, obj):
        material = None
        # Ensure the object has a material slot
        if not obj.data.materials:
            # Create a new material
            material = bpy.data.materials.new(name="Material")
            obj.data.materials.append(material)
        else:
            # Get the first material if one already exists
            material = obj.data.materials[0]

        # Check if the material uses nodes
        if not material.use_nodes:
            material.use_nodes = True

        # Access the node tree
        node_tree = material.node_tree

        # Clear existing nodes
        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        geometry = self.create_node(node_tree, 'ShaderNodeNewGeometry')
        geometry.location = (0, 0)
        
        
        attribute_normal = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_normal.attribute_type = 'INSTANCER'
        attribute_normal.name = 'normal'
        attribute_normal.location = (200, -100)
        
        multiply_add_a = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_add_a.operation = 'MULTIPLY_ADD'
        multiply_add_a.inputs[0].default_value = 0.2 
        multiply_add_a.inputs[1].default_value = 1.0 
        multiply_add_a.location = (200, 100)

#        add_node = node_tree.nodes.new(type='ShaderNodeMath')
#        add_node.operation = 'ADD'  

        mix_rgb = node_tree.nodes.new(type='ShaderNodeMix')
        mix_rgb.data_type = 'VECTOR'  
#        mix_rgb.use_clamp = True  
#        mix_rgb.inputs['Fac'].default_value = 1.0  
        mix_rgb.location = (400, 0)
        
        multiply_add_b = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_add_b.operation = 'MULTIPLY_ADD'
        multiply_add_b.inputs[0].default_value = 0.2 
        multiply_add_b.inputs[1].default_value = 1.0 
        multiply_add_b.location = (200, 300)

        multiply_add_c = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_add_c.operation = 'MULTIPLY_ADD'
        multiply_add_c.inputs[0].default_value = 0.02 
        multiply_add_c.inputs[1].default_value = 0.5
        multiply_add_c.location = (200, 500)
        
        attribute_random = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_random.attribute_type = 'INSTANCER'
        attribute_random.name = "normal" 
        attribute_random.location = (-200, 300)
        
        separate_color = node_tree.nodes.new(type='ShaderNodeSeparateColor')
        separate_color.location = (0, 300)
        
        hue_saturation = node_tree.nodes.new(type='ShaderNodeHueSaturation')
        hue_saturation.location = (400, 300)
        
        attribute_uvmap = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_uvmap.attribute_type = 'GEOMETRY'
        attribute_uvmap.name = 'uvmap'
        attribute_uvmap.location = (-200, -400)
        
        image_texture = node_tree.nodes.new(type='ShaderNodeTexImage')
        image_texture.location = (0, -400)
        #TODO: add image 
#        image_path = "/path/to/your/image.jpg" 
#        image = bpy.data.images.load(image_path)
#        image_texture.image = image
        
        multiply = node_tree.nodes.new(type='ShaderNodeMath')
        multiply.operation = 'MULTIPLY'
        multiply.location = (300, -400)
        
        light_path = node_tree.nodes.new(type='ShaderNodeLightPath')
        light_path.location = (0, -700)
        
        mix_float = node_tree.nodes.new(type='ShaderNodeMix')
        mix_float.data_type = 'FLOAT'  
#        mix_float.use_clamp = True  
#        mix_float.inputs['Fac'].default_value = 1.0  
        mix_float.location = (500, -400)
        
        principled_bsdf = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        principled_bsdf.inputs['Metallic'].default_value = 0.387
        principled_bsdf.inputs['Roughness'].default_value = 0.573 
        principled_bsdf.inputs['IOR'].default_value = 1.5  
        principled_bsdf.location = (700, -400)
        
        material_output = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        material_output.location = (1000, -400)
        
    
        node_tree.links.new(geometry.outputs["Normal"], mix_rgb.inputs["A"])
        node_tree.links.new(attribute_normal.outputs["Vector"], mix_rgb.inputs["B"])
        node_tree.links.new(mix_rgb.outputs["Result"], principled_bsdf.inputs["Normal"])
        node_tree.links.new(principled_bsdf.outputs["BSDF"], material_output.inputs["Surface"])
        node_tree.links.new(attribute_uvmap.outputs["Vector"], image_texture.inputs["Vector"])
        node_tree.links.new(image_texture.outputs["Alpha"], multiply.inputs[1])
        node_tree.links.new(light_path.outputs["Is Camera Ray"], multiply.inputs["Value"])
        node_tree.links.new(attribute_normal.outputs["Alpha"], mix_float.inputs["Factor"])
        node_tree.links.new(multiply.outputs["Value"], mix_float.inputs["B"])
        node_tree.links.new(mix_float.outputs["Result"], principled_bsdf.inputs["Alpha"])
        node_tree.links.new(attribute_normal.outputs["Alpha"], mix_rgb.inputs["Factor"])
        node_tree.links.new(multiply_add_c.outputs["Value"], hue_saturation.inputs["Hue"])
        node_tree.links.new(multiply_add_b.outputs["Value"], hue_saturation.inputs["Saturation"])
        node_tree.links.new(multiply_add_a.outputs["Value"], hue_saturation.inputs["Value"])
        node_tree.links.new(hue_saturation.outputs["Color"], principled_bsdf.inputs["Base Color"])
        node_tree.links.new(separate_color.outputs["Red"], multiply_add_c.inputs["Value"])
        node_tree.links.new(separate_color.outputs["Green"], multiply_add_b.inputs["Value"])
        node_tree.links.new(separate_color.outputs["Blue"], multiply_add_a.inputs["Value"])
        node_tree.links.new(attribute_random.outputs["Color"], separate_color.inputs["Color"])


    
    def create_tangent_tracer_group(self, obj, curves):
        # TODO: create the geometry node group that changes the direction of the brush strokes to follow the tangent of the curves
        pass
        
    
    # generate bezier curves on the surface of obj to guide the direction of brush strokes
    # NOTE: work in progress
    # TODO: reduce frequency of curves when mesh is very complicated
    def generate_surface_curves(self, obj, context):
        bm = bmesh.new()   # create an empty BMesh
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # selected_edges = [ e for e in bm.edges if e.select ]
        # verts_on_edge_loop = self.find_edge_loops(selected_edges[0], set(), [])
        initial_loops = self.find_first_loop(bm)
        if initial_loops is None: # couldn't find any valid loops
            return None
        spline_points = []
        visited_edge = set() # searched for edge loop
        expanded_edge = set() # expanded to neighbors
        used_points = set() 
        edge_queue = collections.deque()
        for e, _ in initial_loops:
            edge_queue.append(e.index)
        while len(edge_queue) > 0:
            top = edge_queue.popleft()
            if top in expanded_edge:
                continue
            if top not in visited_edge:
                curr_verts = self.find_edge_loops(bm.edges[top], visited_edge, used_points, edge_queue)
                if len(curr_verts) >= 3:
                    spline_points.append(curr_verts)
                    used_points.update(curr_verts)
            neighbors = self.find_neighboring_edge(bm.edges[top])
            edge_queue.extend(neighbors)
            expanded_edge.add(top)


        print('first loop:', initial_loops)
        print("spline points:", spline_points)
        crv = bpy.data.curves.new('crv', 'CURVE')
        crv.dimensions = '3D'
        for points in spline_points:
            spline = self.create_spline_from_points(bm, crv, points)
        # spline = self.create_spline_from_points(bm, crv, verts_on_edge_loop)
        new_bezier = bpy.data.objects.new('Bezier', crv)
        new_bezier.parent = obj
        context.collection.objects.link(new_bezier)

        modifier = new_bezier.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
        modifier.target = obj

        return new_bezier

    # Find the initial loops to render
    # if there are full cycles, return all the full cycles
    # otherwise, return the longest path 
    def find_first_loop(self, bmesh):
        used_edge = set()
        cycles = []
        longest_path = None
        max_len = 0
        for e in bmesh.edges:
            if e.index in used_edge:
                continue
            verts = self.find_edge_loops(e, used_edge, set(), [])
            if len(verts) >= 3 and len(verts) > max_len:
                max_len = len(verts)
                longest_path = [(e, verts)]
            if len(verts) >= 4 and verts[0] == verts[-1]:
                cycles.append((e, verts))
        if len(cycles) > 0:
            return cycles
        return longest_path

    # given an edge, find the longest edge loop that contains it and return the vertices on that loop
    # stop if the loop hits an used edge or used points
    def find_edge_loops(self, edge, used_edge, used_points, queue):
        verts_on_loop = collections.deque()
        for v in edge.verts:
            if v.index in used_points:
                return verts_on_loop
        if len(edge.link_loops) == 0:
            return verts_on_loop
        used_edge.add(edge.index)
        queue.append(edge.index)
        loop = edge.link_loops[0]
        verts_on_loop.append(loop.vert.index)
        first_loop = loop
        curr_loop = loop
        going_forward = True
        direction_flag = False
        while True:
            next_loop = curr_loop.link_loop_next.link_loop_radial_next.link_loop_next
            expected_vert = curr_loop.link_loop_next.vert.index

            # If this is true then we've looped back to the beginning and are done
            if next_loop == first_loop:
                print("found loop")
                verts_on_loop.append(next_loop.vert.index)
                break

            # make sure the vertex has 4 neighboring edges
            if expected_vert in used_points or next_loop.vert.index != expected_vert \
                or len(next_loop.vert.link_edges) != 4 or len(next_loop.edge.link_faces) != 2:
                # If going_forward then this is the first dead end and we want to go the other way
                if going_forward:
                    going_forward = False
                    if not expected_vert in used_points:
                        verts_on_loop.append(expected_vert)
                    # Return to the starting edge and go the other way
                    if len(edge.link_loops) > 1:
                        curr_loop= edge.link_loops[1]
                        direction_flag = True
                        continue
                    else:
                        break
                else:
                    if not direction_flag and not expected_vert in used_points:
                        verts_on_loop.appendleft(expected_vert)
                    break

            if not direction_flag:
                used_edge.add(next_loop.edge.index)
                queue.append(next_loop.edge.index)
                if going_forward:
                    verts_on_loop.append(next_loop.vert.index)
                else:
                    verts_on_loop.appendleft(next_loop.vert.index)
            else:
                direction_flag = False
            curr_loop = next_loop
        return verts_on_loop

    # given an edge, find neighboring edges that on on the opposite side of it on the same face (if the face consists of 4 edges)
    # this shold only return 1 or 2 neighbors
    def find_neighboring_edge(self, edge):
        if len(edge.link_loops) > 2 or len(edge.link_faces) != 2:
            return []
        neighbor = []
        for loop in edge.link_loops:
            if len(loop.face.verts) != 4:
                continue
            next_loop = loop.link_loop_radial_next.link_loop_next.link_loop_next
            next_face = next_loop.face
            if len(next_face.verts) == 4 and len(next_loop.edge.link_faces) == 2:
                neighbor.append(next_loop.edge.index)
        return neighbor

    # generate a bezier curve given the control points
    # the handles are automatically set by blender
    def create_spline_from_points(self, mesh, crv, points):
        spline = crv.splines.new(type='BEZIER')
        spline.bezier_points.add(len(points)-1)
        for p, vert_idx in zip(spline.bezier_points, points):
            vertex = mesh.verts[vert_idx]
            p.co = vertex.co
            p.handle_left_type = "AUTO"
            p.handle_right_type = "AUTO"
        return spline

          

def menu_func(self, context):
    self.layout.operator(ObjectPainterEffect.bl_idname)

def register():
    bpy.utils.register_class(ObjectPainterEffect)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(ObjectPainterEffect)
    bpy.types.VIEW3D_MT_object.remove(menu_func)


if __name__ == "__main__":
    register()