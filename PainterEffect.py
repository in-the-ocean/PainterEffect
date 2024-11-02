bl_info = {
    "name": "Painter Effect",
    "blender": (2, 80, 0),
    "category": "Object",
}

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
        curves = self.generate_surface_curves(obj)
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

        group_input = self.create_node(node_tree, 'NodeGroupInput')
        distributePoint = self.create_node(node_tree, "GeometryNodeDistributePointsOnFaces")
        distributePoint.inputs[4].default_value = 40
        alignNormal = self.create_node(node_tree, "FunctionNodeAlignRotationToVector")
        grid = self.create_node(node_tree, "GeometryNodeMeshGrid")
        grid.inputs[0].default_value = 0.2
        grid.inputs[1].default_value = 0.2
        instanceOnPoint = self.create_node(node_tree, "GeometryNodeInstanceOnPoints")
        translateBrush = self.create_node(node_tree, "GeometryNodeTranslateInstances")
        joinGeometry = self.create_node(node_tree, "GeometryNodeJoinGeometry")
        group_output = self.create_node(node_tree, 'NodeGroupOutput')
        node_tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        node_tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")


        node_tree.links.new(group_input.outputs["Geometry"], distributePoint.inputs["Mesh"])
        node_tree.links.new(group_input.outputs["Geometry"], joinGeometry.inputs["Geometry"])
        node_tree.links.new(distributePoint.outputs["Points"], instanceOnPoint.inputs["Points"])
        node_tree.links.new(distributePoint.outputs["Normal"], alignNormal.inputs["Vector"])
        node_tree.links.new(alignNormal.outputs["Rotation"], instanceOnPoint.inputs["Rotation"])
        # node_tree.links.new(in_node.outputs["Size X"], grid.inputs["Size X"])
        # node_tree.links.new(in_node.outputs["Size Y"], grid.inputs["Size Y"])
        node_tree.links.new(grid.outputs["Mesh"], instanceOnPoint.inputs["Instance"])
        node_tree.links.new(instanceOnPoint.outputs["Instances"], translateBrush.inputs["Instances"])
        node_tree.links.new(translateBrush.outputs["Instances"], joinGeometry.inputs["Geometry"])
        node_tree.links.new(joinGeometry.outputs["Geometry"], group_output.inputs["Geometry"])

    def create_shader(self, obj):
        # TODO: create the node tree for Shader Editor
        # Handles the randomness of stroke color, texture of brush storkes, etc
        pass
    
    def create_tangent_tracer_group(self, obj, curves):
        # TODO: create the geometry node group that changes the direction of the brush strokes to follow the tangent of the curves
        pass
        
    
    def generate_surface_curves(self, obj):
        # work in progress
        # should generate bezier curves on the surface of obj to guide the direction of brush strokes
        return None
        print('Start')
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)    
            selected = [i for i in bm.verts if i.select == True]
            print('Selected:', selected)
            crv = bpy.data.curves.new('crv', 'CURVE')
            crv.dimensions = '3D'
            spline = crv.splines.new(type='BEZIER')
            spline.bezier_points.add(len(selected)-1)
            for p, vertex in zip(spline.bezier_points, selected):
                print("iterating", p, vertex)
                p.co = vertex.co # (add nurbs weight)
                p.handle_left_type = "AUTO"
                p.handle_right_type = "AUTO"
            new_bezier = bpy.data.objects.new('Bezier', crv)
            new_bezier.parent = obj
            context.collection.objects.link(new_bezier)
            return new_bezier
        else:
            print("Object is not in edit mode.")
          

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