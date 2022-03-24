import maya.cmds as cmds
import pymel.core as pm
import get_ctrl
import slide_fix

# get walk speed
# constrain the character to a motion path
# bake animation to locators
# delete constraint
# bake animation back to controllers
# delete locators
# fix feet sliding problem


def walk_speed(foot_ctrl):
    #calculate the speed of the walk
    value_time_dict = {} #{value: frame num}
    value_list = []
    #find numbers of keyframes and then use them to get times
    numKeyframes = cmds.keyframe(foot_ctrl, at="tz", query=True, keyframeCount=True)
    times = cmds.keyframe(foot_ctrl, at="tz", query=True, index=(0, numKeyframes), timeChange=True)
    values = cmds.keyframe(foot_ctrl, at="tz", query=True, index=(0, numKeyframes), valueChange=True)
    for i in range(0, len(times)):
            value_time_dict[values[i]] = int(times[i])
            value_list.extend(values)
    #print(value_time_dict)

    max_value = max(value_list)
    min_value = min(value_list)
    max_value_frame_num = value_time_dict[max_value]
    min_value_frame_num = value_time_dict[min_value]
    last_frame_num = max([num for num in value_time_dict.values()])
    speed = 0
    if max_value_frame_num < min_value_frame_num:
        speed = (max_value - min_value) / min_value_frame_num - max_value_frame_num
    elif max_value_frame_num > min_value_frame_num:
        speed = (max_value - min_value) / (last_frame_num - max_value_frame_num + min_value_frame_num - 1)
    return speed


def to_motion_path(speed, path, ch_main_ctrl):
    #length of the path
    curve_length = cmds.arclen(path)
    end_frame = curve_length / speed
    #rint(end_frame)
    # front axis:z, up axis:y
    u_value_curve = pm.pathAnimation(ch_main_ctrl, su=0, stu=1, etu=end_frame, fa='z', ua='y', c=path, fm=1)
    cmds.keyTangent(u_value_curve, inTangentType='linear', outTangentType='linear')


def implement_constraint(ch_ctrls, path):
    # ch_ctrls --> {"Namespace_1":{"head":"Namespace_1:Head_ctrl", ....},...}
    if len(ch_ctrls.keys()) == 1:
        ch = list(ch_ctrls.keys())[0]
        ch_main_ctrl = ch_ctrls[ch]["main"]
        to_motion_path(L_speed, path, ch_main_ctrl)


def start_end_frame():
    # start time of playback
    start = cmds.playbackOptions(q=1, min=1)
    # end time of playback
    end = cmds.playbackOptions(q=1, max=1)
    return start, end


def categorize_objects(ch_ctrls):
    # ch_ctrls--> {"Namespace_1":{"head":"Namespace_1:Head_ctrl", ....},...}
    ch_obj_dict = {} #{ch: {A:{obj:LOC_name}, B:{obj:LOC_name}, C:{obj:LOC_name}}}
    for rig_name in ch_ctrls:
        obj_dict = {"A":{}, "B":{}, "C":{}}  # {A:{obj:LOC_name}, B:{obj:LOC_name}, C:{obj:LOC_name}}
        ch_obj_dict[rig_name] = obj_dict
        # A--> main ctrl
        # B--> ctrls that are only used to rotate --->put to follow
        # C--> ctrls that are used to rotate and translate
        type_B_list = ["FKShoulder_R", "FKShoulder_L", "FKHead_M"]
        for obj in ch_ctrls[rig_name].values():
            obj_name = list(obj.split(":"))[-1]
            if obj_name == "Main":
                obj_dict["A"][obj] = ""
            else:
                loc_name = obj + "_LOC_for_bake"
                if obj_name in type_B_list:
                    obj_dict["B"][obj] = loc_name
                else:
                    obj_dict["C"][obj] = loc_name
                cmds.spaceLocator(name=loc_name)
    #print(ch_obj_dict)
    return ch_obj_dict


def loc_bake(ch_obj_dict, start, end):
    # ch_obj_dict --> {'Namespace_1': {'C': {'Namespace_1:PoleLeg_L': 'JNamespace_1:PoleLeg_L_LOC_for_bake'}}}
    # bake animation on locators
    value_needed = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
    count = 0
    percentage_add = 100 / (end - start)
    cmds.progressWindow(title='Locator Bake', progress=count, status='Baking: 0%', isInterruptable=True)
    for frame in range(int(start), int(end + 1)):
        cmds.currentTime(frame, e=1)# move frame
        # Check if the dialog has been cancelled
        if cmds.progressWindow(query=True, isCancelled=True):
            break

        for rig_name in ch_obj_dict.keys():
            for type_name in ch_obj_dict[rig_name]:
                if type_name != "A":
                    for obj in ch_obj_dict[rig_name][type_name]:
                        cmds.matchTransform(ch_obj_dict[rig_name][type_name][obj], obj, scale=0, position=1, rotation=1, pivots=1)
                        for i in range(0, 6):
                            cmds.setKeyframe(ch_obj_dict[rig_name][type_name][obj], at=value_needed[i], time=frame)
        count += percentage_add
        cmds.progressWindow(edit=True, progress=count, status=('Baking: ' + 'count' + '%'))
    cmds.progressWindow(endProgress=1)


def delete_constraint(ch_obj_dict):
    #delete keys on the main ctrl
    #cmds.delete(selected_object, cn=True)
    for rig in ch_obj_dict.keys():
        #delet motion path
        cmds.delete(ch_obj_dict[rig]["A"].keys(), mp=True)


def animation_bake(ch_obj_dict, start, end):
    #bake animation back to controllers
    value_needed = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
    count = 0
    percentage_add = 100 / (end - start)
    cmds.progressWindow(title='Animation Bake', progress=count, status='Baking: 0%', isInterruptable=True)
    for frame in range(int(start), int(end + 1)):
        cmds.currentTime(frame, e=1)# move frame
        # Check if the dialog has been cancelled
        if cmds.progressWindow(query=True, isCancelled=True):
            break

        for rig in ch_obj_dict.keys():
            for type_name in ch_obj_dict[rig]:
                if type_name == "B":
                    for obj in ch_obj_dict[rig][type_name]:
                        cmds.setKeyframe(obj, at='Global', value=0, time=frame) #set to follow
                        cmds.matchTransform(obj, ch_obj_dict[rig][type_name][obj], scale=0, position=1, rotation=1, pivots=1)
                        for i in range(3, 6):
                            cmds.setKeyframe(obj, at=value_needed[i],time=frame)
                elif type_name == "C":
                    for obj in ch_obj_dict[rig][type_name]:
                        cmds.matchTransform(obj, ch_obj_dict[rig][type_name][obj], scale=0, position=1, rotation=1, pivots=1)
                        for i in range(0, 6):
                            cmds.setKeyframe(obj, at=value_needed[i],time=frame)
        count += percentage_add
        cmds.progressWindow(edit=True, progress=count, status=('Baking: ' + 'count' + '%'))
    cmds.progressWindow(endProgress=1)


def delete_loc(ch_obj_dict):
    # ch_obj_dict--> {ch: {A:{obj:LOC_name}, B:{obj:LOC_name}, C:{obj:LOC_name}}}
    for rig in ch_obj_dict.keys():
        for type_name in ch_obj_dict[rig].keys():
            if type_name != "A":
                for obj in ch_obj_dict[rig][type_name]:
                    cmds.delete(ch_obj_dict[rig][type_name][obj])


def walk_along_exe():
    rig_main = cmds.ls(selection=True)
    ch_ctrl = get_ctrl.get_ctrl(rig_main)
    path = cmds.ls(selection=True)[-1]
    implement_constraint(ch_ctrl, path)
    ch_obj_dict = categorize_objects(ch_ctrl)
    start, end = start_end_frame()
    loc_bake(ch_obj_dict, start, end)
    delete_constraint(ch_obj_dict)
    animation_bake(ch_obj_dict, start, end)
    delete_loc(ch_obj_dict)
    slide_fix.fix_execute()


