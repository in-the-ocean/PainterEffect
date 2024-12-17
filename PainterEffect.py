bl_info = {
    "name": "Painter Effect",
    "blender": (2, 80, 0),
    "category": "Object",
}

import collections
import bpy
import bmesh
import math
import os

SHADER_NAME = "painter_brush_material"
GEOMETRY_NAME = "painter_effect_geometry"
CURVE_TANGENT_NAME = "Painter Effect Curve Tangent"
ATTRIBUTE_UVMAP = "brushUV"
ATTRIBUTE_RANDOM = "random"
ATTRIBUTE_NORMAL = "normal"

TARGET_LINE_NUMBER = 50


    
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
        if obj is None:
            print("No active object in the scene.")
            return {'CANCELLED'}
        
        stroke_style = context.scene.stroke_style
        print(stroke_style)

        curves = self.generate_surface_curves(obj, context)
        tangent_group_name = self.create_tangent_tracer_group(obj)
    
        brush_material, existing_img_texture = self.create_shader(obj, stroke_style)
        self.create_geometry_nodes(obj, tangent_group_name, curves, brush_material)

        return {'FINISHED'}



    def create_tangent_tracer_group(self, obj):
        node_tree = bpy.data.node_groups.new(CURVE_TANGENT_NAME, 'GeometryNodeTree')

        node_tree.interface.new_socket(name="Mesh", in_out="INPUT", socket_type="NodeSocketGeometry")
        node_tree.interface.new_socket(name="Instance", in_out="INPUT", socket_type="NodeSocketGeometry")
        node_tree.interface.new_socket(name="Curve", in_out="INPUT", socket_type="NodeSocketObject")
        node_tree.interface.new_socket(name="Density", in_out="INPUT", socket_type="NodeSocketFloat")
        node_tree.interface.new_socket(name="Scale", in_out="INPUT", socket_type="NodeSocketFloat")
        node_tree.interface.new_socket(name="Normal", in_out="OUTPUT", socket_type="NodeSocketVector")
        node_tree.interface.new_socket(name="Instances", in_out="OUTPUT", socket_type="NodeSocketGeometry")

        group_input_1 = self.create_node(node_tree, 'NodeGroupInput')
        group_input_1.location = (-200, 0)

        group_input_2 = self.create_node(node_tree, 'NodeGroupInput')
        group_input_2.location = (-800, 300)

        group_output = self.create_node(node_tree, 'NodeGroupOutput')
        group_output.location = (1200, 0)

        object_info = self.create_node(node_tree, 'GeometryNodeObjectInfo')
        object_info.location = (-600, 300)

        curve_to_mesh = self.create_node(node_tree, 'GeometryNodeCurveToMesh')
        curve_to_mesh.location = (-400, 300)

        mesh_to_curve = self.create_node(node_tree, 'GeometryNodeMeshToCurve')
        mesh_to_curve.location = (-200, 300)

        curve_tangent = self.create_node(node_tree, 'GeometryNodeInputTangent')
        curve_tangent.location = (-200, 400)

        capture_curve_tangent = self.create_node(node_tree, 'GeometryNodeCaptureAttribute')
        capture_curve_tangent.location = (0, 300)
        capture_curve_tangent.capture_items.new("VECTOR", "Tangent")

        curve_to_mesh_2 = self.create_node(node_tree, 'GeometryNodeCurveToMesh')
        curve_to_mesh_2.location = (200, 300)

        sample_nearest = self.create_node(node_tree, 'GeometryNodeSampleNearest')
        sample_nearest.location = (400, 200)

        sample_index = self.create_node(node_tree, 'GeometryNodeSampleIndex')
        sample_index.location = (600, 300)
        sample_index.data_type = "FLOAT_VECTOR"

        default_density = self.create_node(node_tree, 'ShaderNodeValue')
        default_density.label= "Default Density"
        default_density.outputs[0].default_value = self.get_default_density(obj)
        default_density.location = (-200,-300)

        adjusted_density = self.create_node(node_tree, 'ShaderNodeMath')
        adjusted_density.label= "Adjusted Density"
        adjusted_density.operation= 'MULTIPLY'
        adjusted_density.location = (0,-300)

        calculated_size_1 = self.create_node(node_tree, 'ShaderNodeMath')
        calculated_size_1.operation= 'DIVIDE'
        calculated_size_1.inputs[0].default_value= 1
        calculated_size_1.location = (0,-500)

        calculated_size_2 = self.create_node(node_tree, 'ShaderNodeMath')
        calculated_size_2.operation= 'SQRT'
        calculated_size_2.location = (0,-700)

        default_size= self.create_node(node_tree, 'FunctionNodeInputVector')
        default_size.location=  (200,-300)
        default_size.label= "Default Size"
        default_size.vector= (0.6,0.36,0.0)

        size_multiplier= self.create_node(node_tree, 'ShaderNodeCombineXYZ')
        size_multiplier.location= (200,-500)

        scaled_size = self.create_node(node_tree, 'ShaderNodeVectorMath')
        scaled_size.operation = 'MULTIPLY'
        scaled_size.location = (500,-200)

        adjusted_size= self.create_node(node_tree, 'ShaderNodeVectorMath')
        adjusted_size.operation = 'MULTIPLY_ADD'
        adjusted_size.inputs[2].default_value[2]=0.05
        adjusted_size.label= "Adjusted Size"
        adjusted_size.location = (700,-200)

        distributePoint = self.create_node(node_tree, "GeometryNodeDistributePointsOnFaces")
        distributePoint.location = (200, 0)

        instanceOnPoint = self.create_node(node_tree, "GeometryNodeInstanceOnPoints")
        instanceOnPoint.location = (1000, 0)

        alignNormal = self.create_node(node_tree, "FunctionNodeAlignRotationToVector")
        alignNormal.location = (500, 0)

        align_tangent= self.create_node(node_tree, "FunctionNodeAlignRotationToVector")
        align_tangent.location = (700, 0)
        align_tangent.axis = "Y"
        align_tangent.pivot_axis = "Z"

        node_tree.links.new(group_input_1.outputs["Mesh"], distributePoint.inputs["Mesh"])
        node_tree.links.new(group_input_1.outputs["Instance"], instanceOnPoint.inputs["Instance"])
        node_tree.links.new(distributePoint.outputs["Points"], instanceOnPoint.inputs["Points"])
        node_tree.links.new(distributePoint.outputs["Normal"], group_output.inputs["Normal"])
        node_tree.links.new(distributePoint.outputs["Normal"], alignNormal.inputs["Vector"])
        node_tree.links.new(alignNormal.outputs["Rotation"], align_tangent.inputs["Rotation"])
        node_tree.links.new(align_tangent.outputs["Rotation"], instanceOnPoint.inputs["Rotation"])
        node_tree.links.new(instanceOnPoint.outputs["Instances"], group_output.inputs["Instances"])
        node_tree.links.new(group_input_2.outputs["Curve"], object_info.inputs["Object"])
        node_tree.links.new(object_info.outputs["Geometry"], curve_to_mesh.inputs["Curve"])
        node_tree.links.new(curve_to_mesh.outputs["Mesh"], mesh_to_curve.inputs["Mesh"])
        node_tree.links.new(mesh_to_curve.outputs["Curve"], capture_curve_tangent.inputs["Geometry"])
        node_tree.links.new(curve_tangent.outputs["Tangent"], capture_curve_tangent.inputs["Tangent"])
        node_tree.links.new(capture_curve_tangent.outputs[0], curve_to_mesh_2.inputs["Curve"])
        node_tree.links.new(capture_curve_tangent.outputs[1], sample_index.inputs["Value"])
        node_tree.links.new(curve_to_mesh_2.outputs["Mesh"], sample_nearest.inputs["Geometry"])
        node_tree.links.new(curve_to_mesh_2.outputs["Mesh"], sample_index.inputs["Geometry"])
        node_tree.links.new(sample_nearest.outputs["Index"], sample_index.inputs["Index"])
        node_tree.links.new(sample_index.outputs["Value"], align_tangent.inputs["Vector"])
        
        node_tree.links.new(default_density.outputs["Value"], adjusted_density.inputs[0])
        node_tree.links.new(group_input_1.outputs["Density"], adjusted_density.inputs[1])
        node_tree.links.new(adjusted_density.outputs["Value"], distributePoint.inputs["Density"])
        node_tree.links.new(group_input_1.outputs["Density"], calculated_size_1.inputs[1])
        node_tree.links.new(calculated_size_1.outputs["Value"], calculated_size_2.inputs["Value"])
        node_tree.links.new(calculated_size_2.outputs["Value"], size_multiplier.inputs["X"])
        node_tree.links.new(calculated_size_2.outputs["Value"], size_multiplier.inputs["Y"])
        node_tree.links.new(calculated_size_2.outputs["Value"], size_multiplier.inputs["Z"])
        node_tree.links.new(default_size.outputs["Vector"], scaled_size.inputs[0])
        node_tree.links.new(group_input_1.outputs["Scale"], scaled_size.inputs[1])
        node_tree.links.new(scaled_size.outputs["Vector"], adjusted_size.inputs[0])
        node_tree.links.new(size_multiplier.outputs["Vector"], adjusted_size.inputs[1])
        node_tree.links.new(adjusted_size.outputs["Vector"], instanceOnPoint.inputs["Scale"])
        
        # Curvature 
        capture_normal = self.create_node(node_tree, "GeometryNodeCaptureAttribute")
        capture_normal.domain = "POINT"
        capture_normal.location = (200, 100)

        sample_nearest_curvature = self.create_node(node_tree, "GeometryNodeSampleNearest")
        sample_nearest_curvature.location = (400, 100)

        subtract_normals = self.create_node(node_tree, "ShaderNodeVectorMath")
        subtract_normals.operation = "SUBTRACT"
        subtract_normals.location = (600, 100)

        curvature_length = self.create_node(node_tree, "ShaderNodeVectorMath")
        curvature_length.operation = "LENGTH"
        curvature_length.location = (800, 100)

        map_range = self.create_node(node_tree, "ShaderNodeMapRange")
        map_range.inputs["From Min"].default_value = 0.0
        map_range.inputs["From Max"].default_value = 0.5
        map_range.inputs["To Min"].default_value = 0.5
        map_range.inputs["To Max"].default_value = 1.5
        map_range.clamp = True
        map_range.location = (1000, 100)

        multiply_scale = self.create_node(node_tree, "ShaderNodeVectorMath")
        multiply_scale.operation = "MULTIPLY"
        multiply_scale.location = (1200, 100)

        node_tree.links.new(distributePoint.outputs["Points"], capture_normal.inputs["Geometry"])
        node_tree.links.new(capture_normal.outputs["Geometry"], sample_nearest_curvature.inputs["Sample Position"])
        node_tree.links.new(sample_nearest_curvature.outputs["Index"], subtract_normals.inputs[1])
        node_tree.links.new(capture_normal.outputs["Geometry"], subtract_normals.inputs[0])
        node_tree.links.new(subtract_normals.outputs["Vector"], curvature_length.inputs[0])
        node_tree.links.new(curvature_length.outputs["Value"], map_range.inputs["Value"])
        node_tree.links.new(map_range.outputs["Result"], multiply_scale.inputs[1])
        node_tree.links.new(group_input_1.outputs["Scale"], multiply_scale.inputs[0])
        node_tree.links.new(multiply_scale.outputs["Vector"], instanceOnPoint.inputs["Scale"])

        return node_tree.name

    
    
    def create_geometry_nodes(self, obj, tangent_group_name, bezier_curve, brush_material):
            
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

            node_tree = bpy.data.node_groups.new(GEOMETRY_NAME, 'GeometryNodeTree')
            # Get the node tree
            modifier.node_group = node_tree
        if node_tree is None:
            self.report({'ERROR'}, "Failed to create or access the Geometry Nodes node tree.")
            return 
        node_tree.nodes.clear()

   
        group_input = self.create_node(node_tree, 'NodeGroupInput')
        group_input.location = (0, 0)

        brush_panel = node_tree.interface.new_panel(name = "Brush Parameters")
        brush_density = node_tree.interface.new_socket(name="Density", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = brush_panel)
        obj.modifiers["GeometryNodes"]["Socket_1"]= 1.0
        brush_density.min_value = 0.0
        brush_density.max_value = 10.0
        brush_scale_X = node_tree.interface.new_socket(name="Scale: X", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = brush_panel)
        obj.modifiers["GeometryNodes"]["Socket_2"]= 1.0
        brush_scale_X.min_value = 0.0
        brush_scale_X.max_value = 10.0
        brush_scale_Y = node_tree.interface.new_socket(name="Scale: Y", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = brush_panel)
        obj.modifiers["GeometryNodes"]["Socket_3"]= 1.0
        brush_scale_Y.min_value = 0.0
        brush_scale_Y.max_value = 10.0
        brush_scale_Z = node_tree.interface.new_socket(name="Scale: Z", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = brush_panel)
        brush_scale_Z.default_value = 1.0
        brush_scale_Z.hide_in_modifier= True
        
        color_value_panel = node_tree.interface.new_panel(name = "Color Value")
        hue_value = node_tree.interface.new_socket(name="Hue", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_value_panel)
        obj.modifiers["GeometryNodes"]["Socket_6"]=0.0
        hue_value.min_value = -10.0
        hue_value.max_value = 10.0
        saturation_value = node_tree.interface.new_socket(name="Saturation",in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_value_panel)
        obj.modifiers["GeometryNodes"]["Socket_7"]=0.0
        saturation_value.min_value = -10.0
        saturation_value.max_value = 10.0
        brightness_value = node_tree.interface.new_socket(name="Brightness", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_value_panel)
        obj.modifiers["GeometryNodes"]["Socket_8"]=0.0
        brightness_value.min_value = -10.0
        brightness_value.max_value = 10.0

        color_randomness_panel = node_tree.interface.new_panel(name = "Color Randomness")
        hue_randomness = node_tree.interface.new_socket(name="Hue", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_randomness_panel)
        obj.modifiers["GeometryNodes"]["Socket_10"]=1.0
        hue_randomness.min_value = 0.0
        hue_randomness.max_value = 10.0
        saturation_randomness = node_tree.interface.new_socket(name="Saturation",in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_randomness_panel)
        obj.modifiers["GeometryNodes"]["Socket_11"]=1.0
        saturation_randomness.min_value = 0.0
        saturation_randomness.max_value = 10.0
        brightness_randomness = node_tree.interface.new_socket(name="Brightness", in_out='INPUT', socket_type= 'NodeSocketFloat', parent = color_randomness_panel)
        obj.modifiers["GeometryNodes"]["Socket_12"]=1.0
        brightness_randomness.min_value = 0.0
        brightness_randomness.max_value = 10.0

        brush_scale = self.create_node(node_tree, "ShaderNodeCombineXYZ")
        brush_scale.label = "Brush Scale"
        brush_scale.location = (200,200)

        tangent_transfer = self.create_node(node_tree, "GeometryNodeGroup")
        tangent_transfer.node_tree = bpy.data.node_groups[tangent_group_name]
        tangent_transfer.inputs[2].default_value = bezier_curve
        tangent_transfer.location = (400, 200)

        grid = self.create_node(node_tree, "GeometryNodeMeshGrid")
        grid.inputs[0].default_value, grid.inputs[1].default_value = self.get_default_grid_size(obj)
        grid.location = (200, -100)
        
        store_uv_map = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_uv_map.inputs["Name"].default_value = ATTRIBUTE_UVMAP
        store_uv_map.data_type = 'FLOAT_VECTOR'
        store_uv_map.domain = "POINT" 
        store_uv_map.location = (400, -100)
        
        translateBrush = self.create_node(node_tree, "GeometryNodeTranslateInstances")
        translateBrush.location = (800, 200)
        translateBrush.inputs['Translation'].default_value[2] = self.get_default_translate_z(obj)
        
        store_normal = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_normal.inputs["Name"].default_value = ATTRIBUTE_NORMAL
        store_normal.data_type = 'FLOAT_VECTOR'
        store_normal.domain = "INSTANCE" 
        store_normal.location = (1000, 0)

        color_value = self.create_node(node_tree, "ShaderNodeCombineXYZ")
        color_value.label = "Color Value"
        color_value.location = (800,700)
        
        color_randomness = self.create_node(node_tree, "ShaderNodeCombineXYZ")
        color_randomness.label = "Color Randomness"
        color_randomness.location = (800,500)

        color_subtract = self.create_node(node_tree, "ShaderNodeMath")
        color_subtract.label = "Color Substract"
        color_subtract.operation= 'SUBTRACT'
        color_subtract.location = (1000,700)

        color_add = self.create_node(node_tree, "ShaderNodeMath")
        color_add.label = "Color Add"
        color_add.location = (1000,500)

        random_value = self.create_node(node_tree, "FunctionNodeRandomValue")
        random_value.data_type = 'FLOAT_VECTOR'
        random_value.label = "Color Adjustment Node"
        random_value.data_type = 'FLOAT_VECTOR'
        random_value.location = (1000, 300)
                
        store_random = self.create_node(node_tree, "GeometryNodeStoreNamedAttribute")
        store_random.inputs["Name"].default_value = ATTRIBUTE_RANDOM
        store_random.data_type = 'FLOAT_VECTOR'
        store_random.domain = "INSTANCE" 
        store_random.location = (1200, 0)
        
        joinGeometry = self.create_node(node_tree, "GeometryNodeJoinGeometry")
        joinGeometry.location = (1600, 0)
        
        set_material = self.create_node(node_tree, "GeometryNodeSetMaterial")
        set_material.location = (1400, 0)
        set_material.inputs[2].default_value = brush_material
        
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
        
        node_tree.links.new(group_input.outputs["Geometry"], tangent_transfer.inputs["Mesh"])
        node_tree.links.new(group_input.outputs["Density"],tangent_transfer.inputs["Density"])
        node_tree.links.new(group_input.outputs["Scale: X"], brush_scale.inputs["X"])
        node_tree.links.new(group_input.outputs["Scale: Y"], brush_scale.inputs["Y"])
        node_tree.links.new(group_input.outputs["Scale: Z"], brush_scale.inputs["Z"])
        node_tree.links.new(brush_scale.outputs["Vector"],tangent_transfer.inputs["Scale"])
        node_tree.links.new(group_input.outputs[5], color_value.inputs["X"])
        node_tree.links.new(group_input.outputs[6], color_value.inputs["Y"])
        node_tree.links.new(group_input.outputs[7], color_value.inputs["Z"])
        node_tree.links.new(group_input.outputs[8], color_randomness.inputs["X"])
        node_tree.links.new(group_input.outputs[9], color_randomness.inputs["Y"])
        node_tree.links.new(group_input.outputs[10], color_randomness.inputs["Z"])
        node_tree.links.new(color_value.outputs["Vector"], color_subtract.inputs[0])
        node_tree.links.new(color_randomness.outputs["Vector"], color_subtract.inputs[1])
        node_tree.links.new(color_value.outputs["Vector"], color_add.inputs[0])
        node_tree.links.new(color_randomness.outputs["Vector"], color_add.inputs[1])
        node_tree.links.new(color_subtract.outputs["Value"], random_value.inputs["Min"])
        node_tree.links.new(color_add.outputs["Value"], random_value.inputs["Max"])
        node_tree.links.new(grid.outputs["Mesh"], store_uv_map.inputs["Geometry"])
        node_tree.links.new(grid.outputs["UV Map"], store_uv_map.inputs["Value"])
        node_tree.links.new(store_uv_map.outputs["Geometry"], tangent_transfer.inputs["Instance"])
        node_tree.links.new(tangent_transfer.outputs["Instances"], translateBrush.inputs["Instances"])
        node_tree.links.new(translateBrush.outputs["Instances"], store_normal.inputs["Geometry"])
        node_tree.links.new(random_value.outputs["Value"], store_random.inputs["Value"])
        node_tree.links.new(store_normal.outputs["Geometry"], store_random.inputs["Geometry"])
        node_tree.links.new(store_random.outputs["Geometry"], set_material.inputs["Geometry"])
        node_tree.links.new(set_material.outputs["Geometry"], joinGeometry.inputs["Geometry"])

        node_tree.links.new(group_input.outputs["Geometry"], joinGeometry.inputs["Geometry"])
        node_tree.links.new(self_object.outputs["Self Object"], object_info.inputs["Object"])
        node_tree.links.new(object_info.outputs["Rotation"], vector_rotate.inputs["Rotation"])
        node_tree.links.new(tangent_transfer.outputs["Normal"], vector_rotate.inputs["Vector"])
        node_tree.links.new(vector_rotate.outputs["Vector"], store_normal.inputs["Value"])
        node_tree.links.new(joinGeometry.outputs["Geometry"], group_output.inputs["Geometry"])



    def create_shader(self, obj, stroke_style):
        material = None
        for m in obj.data.materials:
            if m.name.startswith(SHADER_NAME):
                return (m, None)

        for slot in obj.material_slots:
            if slot.material and slot.material.name.startswith(SHADER_NAME):
                obj.data.materials.pop(index=obj.material_slots[:].index(slot))
            
        existing_material = obj.active_material
        default_img = None
        default_color = (0.506, 0.8, 0.192, 1)
        
        if existing_material is not None and existing_material.node_tree is not None:
            nodes = existing_material.node_tree.nodes
            principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
            base_color = principled.inputs['Base Color']
            print("current base color", base_color)
            if len(base_color.links) > 0:
                from_node = base_color.links[0].from_node
                if type(from_node) is bpy.types.ShaderNodeTexImage:
                    default_img = from_node.image
            else:
                default_color = base_color.default_value
        else:
            existing_material = bpy.data.materials.new(name="Material")
            existing_material.use_nodes = True

            # Get the Principled BSDF node 
            bsdf = existing_material.node_tree.nodes.get('Principled BSDF')

            # Set the base color of the material 
            bsdf.inputs['Base Color'].default_value = default_color
            obj.data.materials.append(existing_material)
            obj.active_material = existing_material

#        material = bpy.data.materials.new(name=SHADER_NAME)
#        obj.data.materials.append(material)
#        material.surface_render_method = "BLENDED"

#        # Check if the material uses nodes
#        if not material.use_nodes:
#            material.use_nodes = True

#        # Access the node tree
#        node_tree = material.node_tree

#        # Clear existing nodes
#        for node in node_tree.nodes:
#            node_tree.nodes.remove(node)
        material = bpy.data.materials.new(name=SHADER_NAME)
        obj.data.materials.append(material)
        obj.active_material = material
        material.use_nodes = True
        node_tree = material.node_tree
        node_tree.nodes.clear()

        geometry = self.create_node(node_tree, 'ShaderNodeNewGeometry')
        geometry.location = (0, 0)
        
        
        attribute_normal = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_normal.attribute_type = 'INSTANCER'
        attribute_normal.attribute_name = ATTRIBUTE_NORMAL
        # attribute_normal.inputs["Name"].default_value = "normal" 
        attribute_normal.location = (200, -100)
        
        multiply_add_a = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_add_a.operation = 'MULTIPLY_ADD'
        multiply_add_a.inputs[1].default_value = 0.2 #multiplier
        multiply_add_a.inputs[2].default_value = 1.0 #addend
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
        multiply_add_b.inputs[1].default_value = 0.2 #multiplier
        multiply_add_b.inputs[2].default_value = 1.0 #addend
        multiply_add_b.location = (200, 300)

        multiply_add_c = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_add_c.operation = 'MULTIPLY_ADD'
        multiply_add_c.inputs[1].default_value = 0.02  #multiplier
        multiply_add_c.inputs[2].default_value = 0.5  #addend
        multiply_add_c.location = (200, 500)
        
        attribute_random = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_random.attribute_type = 'INSTANCER'
        attribute_random.attribute_name = ATTRIBUTE_RANDOM
        attribute_random.location = (-200, 300)
        
        separate_color = node_tree.nodes.new(type='ShaderNodeSeparateColor')
        separate_color.location = (0, 300)
        
        hue_saturation = node_tree.nodes.new(type='ShaderNodeHueSaturation')
        hue_saturation.location = (400, 300)
        hue_saturation.inputs[4].default_value = (0.506, 0.8, 0.192, 1) if default_color is None else default_color
        if default_img is not None:
            img_texture = node_tree.nodes.new(type="ShaderNodeTexImage")
            img_texture.image = default_img
            attribute_uv = node_tree.nodes.new(type='ShaderNodeAttribute')
            attribute_uv.attribute_type = 'INSTANCER'
            attribute_uv.attribute_name = 'UVMap'
        
        attribute_brushuv = node_tree.nodes.new(type='ShaderNodeAttribute')
        attribute_brushuv.attribute_type = 'GEOMETRY'
        attribute_brushuv.attribute_name = ATTRIBUTE_UVMAP
        attribute_brushuv.location = (-200, -400)
        
        brush_texture = node_tree.nodes.new(type='ShaderNodeTexImage')
        brush_texture.location = (0, -400)

        # image_path = "stroke.png" 
        # image = bpy.data.images.load(image_path)
        # image_texture.image = image
        # TODO: this iswhen the png is the same directory as the current blend
        blend_file_directory = os.path.dirname(bpy.data.filepath)
        image_path = os.path.join(blend_file_directory, stroke_style)

#        print(bpy.data.filepath, blend_file_directory, image_path)
        if os.path.exists(image_path):
            # Check if the image is already loaded to avoid duplicates
            image_name = os.path.basename(image_path)
            if image_name in bpy.data.images:
                image = bpy.data.images[image_name]
            else:
                image = bpy.data.images.load(image_path)
            
            # Update the existing brush_texture node with the new image
            brush_texture.image = image
            brush_texture.interpolation = 'Smart'
            brush_texture.extension = 'REPEAT'
            
            # Force Blender to refresh the shader
            bpy.context.view_layer.update()
            bpy.context.scene.update()
        else:
            self.report({'ERROR'}, f"Cannot find image file: {stroke_style}")


        
        multiply = node_tree.nodes.new(type='ShaderNodeMath')
        multiply.operation = 'MULTIPLY'
        multiply.location = (300, -400)
        
        light_path = node_tree.nodes.new(type='ShaderNodeLightPath')
        light_path.location = (0, -700)
        
        mix_float = node_tree.nodes.new(type='ShaderNodeMix')
        mix_float.data_type = 'FLOAT'  
#        mix_float.use_clamp = True  
        mix_float.inputs['A'].default_value = 1.0  
        mix_float.location = (500, -400)
        
        principled_bsdf = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        if existing_material is not None and existing_material.node_tree is not None:
            nodes = existing_material.node_tree.nodes
            principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
            principled_bsdf.inputs['Metallic'].default_value = principled.inputs['Metallic'].default_value
            principled_bsdf.inputs['Roughness'].default_value = principled.inputs['Roughness'].default_value
            principled_bsdf.inputs['IOR'].default_value = principled.inputs['IOR'].default_value
        else:
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
        node_tree.links.new(attribute_brushuv.outputs["Vector"], brush_texture.inputs["Vector"])
        node_tree.links.new(brush_texture.outputs["Alpha"], multiply.inputs[1])
        node_tree.links.new(light_path.outputs["Is Camera Ray"], multiply.inputs["Value"])
        node_tree.links.new(attribute_normal.outputs["Alpha"], mix_float.inputs["Factor"])
        node_tree.links.new(multiply.outputs["Value"], mix_float.inputs["B"])
        node_tree.links.new(mix_float.outputs["Result"], principled_bsdf.inputs["Alpha"])
        node_tree.links.new(attribute_normal.outputs["Alpha"], mix_rgb.inputs["Factor"])

        node_tree.links.new(multiply_add_c.outputs["Value"], hue_saturation.inputs["Hue"])
        node_tree.links.new(multiply_add_b.outputs["Value"], hue_saturation.inputs["Saturation"])
        node_tree.links.new(multiply_add_a.outputs["Value"], hue_saturation.inputs["Value"])
        if default_img is not None:
            node_tree.links.new(attribute_uv.outputs["Vector"], img_texture.inputs["Vector"])
            node_tree.links.new(img_texture.outputs["Color"], hue_saturation.inputs["Color"])

        node_tree.links.new(hue_saturation.outputs["Color"], principled_bsdf.inputs["Base Color"])
        node_tree.links.new(separate_color.outputs["Red"], multiply_add_c.inputs["Value"])
        node_tree.links.new(separate_color.outputs["Green"], multiply_add_b.inputs["Value"])
        node_tree.links.new(separate_color.outputs["Blue"], multiply_add_a.inputs["Value"])
        node_tree.links.new(attribute_random.outputs["Color"], separate_color.inputs["Color"])


        if material.name not in obj.data.materials:
            obj.data.materials.append(material)
            obj.active_material = material
            bpy.context.view_layer.update()
    
        return (material, default_img)

    
    
    
    # generate bezier curves on the surface of obj to guide the direction of brush strokes
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


        # print('first loop:', initial_loops)
        # print("spline points:", spline_points)
        crv = bpy.data.curves.new('crv', 'CURVE')
        crv.dimensions = '3D'
        sampling = math.floor(len(spline_points) / TARGET_LINE_NUMBER)
        for i in range(0, len(spline_points), max(sampling, 1)):
            spline = self.create_spline_from_points(bm, crv, spline_points[i])
        # spline = self.create_spline_from_points(bm, crv, verts_on_edge_loop)
        new_bezier = bpy.data.objects.new('Bezier', crv)
        new_bezier.parent = obj
        context.collection.objects.link(new_bezier)

        # modifier = new_bezier.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
        # modifier.target = obj

        return new_bezier



    def get_default_density(self, obj):
        min_extent = self.get_obj_size(obj)
        return 1500 / min_extent**2



    def get_default_grid_size(self, obj):
        min_extent = self.get_obj_size(obj)
        return (min_extent / 15, min_extent / 3)



    def get_default_translate_z(self, obj):
        min_extent = self.get_obj_size(obj)
        return min_extent / 10



    def get_obj_size(self, obj):
        dims = obj.dimensions
        return (dims.x + dims.y + dims.z) / 3



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
                # print("found loop")
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
    


class ObjectPainterEffect_Panel(bpy.types.Panel):
    bl_label = "Painter Effect Tools"
    bl_idname = "OBJECT_PT_painter_effect_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"


    def draw(self, context):
        layout = self.layout
        object = context.object

        if object is None:
            layout.label(text="No active object selected")
            return

        layout.operator("object.painter_effect", text= "Apply Painter Effect")
        layout.prop(context.scene, "stroke_style", text="Stroke Style") 


def menu_func(self, context):
    self.layout.operator(ObjectPainterEffect.bl_idname)


def load_stroke_images_callback(self, context):
    image_dir = os.path.dirname(bpy.data.filepath)
    images = []
    if os.path.exists(image_dir):
        for file in os.listdir(image_dir):
            if file.lower().endswith('.png'):
                images.append((file, file, f"Use {file} as stroke style"))
    if not images:
        images.append(("None", "None", "No images found"))
    
    return images


def register():
    bpy.types.Scene.stroke_style = bpy.props.EnumProperty(
        name="Stroke Style",
        description="Choose the stroke style",
        items=load_stroke_images_callback
    )
    
    bpy.types.VIEW3D_MT_object.append(menu_func)
    bpy.utils.register_class(ObjectPainterEffect)
    bpy.utils.register_class(ObjectPainterEffect_Panel)
        
        
       
def unregister():
    del bpy.types.Scene.stroke_style
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    bpy.utils.unregister_class(ObjectPainterEffect)
    bpy.utils.unregister_class(ObjectPainterEffect_Panel)
    


if __name__ == "__main__":
    register()