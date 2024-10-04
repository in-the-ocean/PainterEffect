bl_info = {
    "name": "Painter Effect",
    "blender": (2, 80, 0),
    "category": "Object",
}

import bpy


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
        node_tree = None

        # Check if the object has a geometry nodes modifier
        if obj.modifiers and obj.modifiers.get("GeometryNodes"):
            # Get the geometry nodes modifier
            modifier = obj.modifiers["GeometryNodes"]

            # Access the node tree
            node_tree = modifier.node_group
        else:
            modifier = obj.modifiers.new(name="GeometryNodes", type='NODES')

            # Get the node tree
            node_tree = modifier.node_group

        node_tree.nodes.clear()

        group_input = self.create_node(node_tree, 'NodeGroupInput')

        distributePoint = self.create_node(node_tree, "GeometryNodeDistributePointsOnFaces")
        alignNormal = self.create_node(node_tree, "FunctionNodeAlignRotationToVector")
        grid = self.create_node(node_tree, "GeometryNodeMeshGrid")
        instanceOnPoint = self.create_node(node_tree, "GeometryNodeInstanceOnPoints")
        translateBrush = self.create_node(node_tree, "GeometryNodeTranslateInstances")
        joinGeometry = self.create_node(node_tree, "GeometryNodeJoinGeometry")
        group_output = self.create_node(node_tree, 'NodeGroupOutput')

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


        return {'FINISHED'}

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