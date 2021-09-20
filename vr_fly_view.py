import bpy
from mathutils import Matrix, Vector, Euler
from math import *


bl_info = {
    "name": "Fly mode for VR Scene Inspection",
    "author": "tuttu",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "description": "You can fly in VR Scene mode with your controller stick",
    "support": "TESTING",
    "warning": "This is limited supported version because VR support for Blender is early preview.",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/3d_view/vr_scene_inspection.html",
    "category": "3D View",
}


ACTION_SET_NAME = 'test_actions'
ACTION_NAME = 'move'
BINDING_THRESHOLD = 0.0001
COMMAND_CALL_INTERVAL = 0.03
USER_PATH_LEFT = '/user/hand/left'
USER_PATH_RIGHT = '/user/hand/right'

SPEED_MOVE = 0.1
SPEED_ROTATION = 0.05

controller_bindings = [
    {
        'name': 'windows_mr',
        'profile': '/interaction_profiles/microsoft/motion_controller',
        'component_path': '/input/thumbstick',
    },
    {
        'name': 'oculus_touch',
        'profile': '/interaction_profiles/oculus/touch_controller',
        'component_path': '/input/thumbstick',
    },
    {
        'name': 'valve_index',
        'profile': '/interaction_profiles/valve/index_controller',
        'component_path': '/input/thumbstick',
    },
    {
        'name': 'vive_controller',
        'profile': '/interaction_profiles/htc/vive_controller',
        'component_path': '/input/trackpad',
    },
    {
        'name': 'google_daydream',
        'profile': '/interaction_profiles/google/daydream_controller',
        'component_path': '/input/trackpad',
    },
]


class VIEW3D_PT_vr_info(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "VR Info"

    @classmethod
    def poll(cls, context):
        return not bpy.app.build_options.xr_openxr

    def draw(self, context):
        layout = self.layout
        layout.label(icon='ERROR', text="Built without VR/OpenXR features")


def create_item(actionmap):
    item = actionmap.actionmap_items.new(ACTION_NAME, True)
    item.type = 'VECTOR2D'
    item.user_path0 = USER_PATH_RIGHT
    item.user_path1 = USER_PATH_LEFT
    return item


def create_binding(item, name, profile, component_path):
    binding = item.bindings.new(name, True)
    binding.profile = profile
    binding.component_path0 = component_path
    binding.component_path1 = component_path
    binding.threshold = BINDING_THRESHOLD
    return binding


def create_bindings(session, item, actionmap):
    for binding_setting in controller_bindings:
        binding = create_binding(item, **binding_setting)
        session.action_binding_create(bpy.context, actionmap, item, binding)


def xr_handler(scene):
    session = bpy.context.window_manager.xr_session_state
    actionmap = session.actionmaps.new(session, ACTION_SET_NAME, True)
    item = create_item(actionmap)
    session.action_set_create(bpy.context, actionmap)
    session.action_create(bpy.context, actionmap, item)
    create_bindings(session, item, actionmap)
    session.active_action_set_set(bpy.context, ACTION_SET_NAME)

    bpy.app.timers.register(controller_event_handler)


def get_viewer_rotation_matrix(session):
    rot = session.viewer_pose_rotation
    rotmat = Matrix.Identity(3)
    rotmat.rotate(rot)
    rotmat.resize_4x4()
    return rotmat


def calc_horizontal_movement(dx, dy, viewer_rotation):
    vec = Vector((dx * SPEED_MOVE, 0, -dy * SPEED_MOVE))
    vec.rotate(viewer_rotation)
    return Matrix.Translation(vec)


def calc_horizontal_rotation(dx, dy):
    return Euler((0, 0, -dx * SPEED_ROTATION), 'XYZ').to_matrix().to_4x4()


def global_transform(original, transform):
    _, rot, _ = original.decompose()
    rotmat = rot.to_matrix().to_4x4()
    return rotmat.inverted() @ transform @ rotmat


def apply_transform_to_landmark(scene, transform):
    landmarks = scene.vr_landmarks
    for lm in landmarks:
        if ((lm.type == 'SCENE_CAMERA' and not scene.camera) or
                (lm.type == 'USER_CAMERA' and not lm.base_pose_camera)):
            continue
        if lm.type == 'SCENE_CAMERA':
            scene.camera.matrix_world @= global_transform(
                scene.camera.matrix_world, transform)
        elif lm.type == 'USER_CAMERA':
            lm.base_pose_camera.matrix_world @= global_transform(
                lm.base_pose_camera.matrix_world, transform)


def over_threshold(dx, dy):
    return abs(dx) > BINDING_THRESHOLD or abs(dy) > BINDING_THRESHOLD


def controller_event_handler():
    if not bpy.types.XrSessionState.is_running(bpy.context):
        print('VR session is not running')
        return None

    session = bpy.context.window_manager.xr_session_state
    action_state_left = session.action_state_get(
        bpy.context, ACTION_SET_NAME, ACTION_NAME, USER_PATH_LEFT)
    action_state_right = session.action_state_get(
        bpy.context, ACTION_SET_NAME, ACTION_NAME, USER_PATH_RIGHT)

    if not over_threshold(*action_state_left) and \
            not over_threshold(*action_state_right):
        return COMMAND_CALL_INTERVAL

    viewer_rotation = get_viewer_rotation_matrix(session)
    hor = calc_horizontal_movement(*action_state_left, viewer_rotation)
    rot = calc_horizontal_rotation(*action_state_right)
    apply_transform_to_landmark(bpy.context.scene, hor @ rot)
    return COMMAND_CALL_INTERVAL


def register():
    if not bpy.app.build_options.xr_openxr:
        bpy.utils.register_class(VIEW3D_PT_vr_info)
        return

    bpy.app.handlers.xr_session_start_pre.append(xr_handler)


def unregister():
    if not bpy.app.build_options.xr_openxr:
        bpy.utils.unregister_class(VIEW3D_PT_vr_info)
        return

    bpy.app.handlers.xr_session_start_pre.remove(xr_handler)


if __name__ == "__main__":
    register()
