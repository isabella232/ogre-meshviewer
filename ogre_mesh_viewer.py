import Ogre
import Ogre.RTShader as OgreRTShader
import Ogre.Bites as OgreBites
import Ogre.Overlay

import Ogre.ImGui as ImGui

import os.path

RGN_MESHVIEWER = "OgreMeshViewer"

VES2STR = ("ERROR", "Position", "Blend Weights", "Blend Indices", "Normal", "Diffuse", "Specular", "Texcoord", "Binormal", "Tangent")
VET2STR = ("float", "float2", "float3", "float4", "ERROR",
           "short", "short2", "short3", "short4", "ubyte4", "argb", "abgr",
           "double", "double2", "double3", "double4",
           "ushort", "ushort2", "ushort3", "ushort4",
           "int", "int2", "int3", "int4",
           "uint", "uint2", "uint3", "uint4",
           "byte4", "byte4n", "ubyte4n", "short2n", "short4n", "ushort2n", "ushort4n", "int1010102n")

ROP2STR = ("ERROR", "Point List", "Line List", "Line Strip", "Triangle List", "Triangle Strip", "Triangle Fan")

def show_vertex_decl(decl):
    ImGui.Columns(2)
    ImGui.Text("Semantic")
    ImGui.NextColumn()
    ImGui.Text("Type")
    ImGui.NextColumn()
    ImGui.Separator()

    for e in decl.getElements():
        ImGui.Text(VES2STR[e.getSemantic()])
        ImGui.NextColumn()
        ImGui.Text(VET2STR[e.getType()])
        ImGui.NextColumn()
    ImGui.Columns(1)

def printable(str):
    return str.encode("utf-8", "replace").decode()

class MaterialCreator(Ogre.MeshSerializerListener):

    def __init__(self):
        Ogre.MeshSerializerListener.__init__(self)

    def processMaterialName(self, mesh, name):
        # ensure some material exists so we can display the name
        mat_mgr = Ogre.MaterialManager.getSingleton()
        if not mat_mgr.resourceExists(name, mesh.getGroup()):
            lmgr = Ogre.LogManager.getSingleton()
            try:
                mat = mat_mgr.create(name, mesh.getGroup())
                lmgr.logWarning("could not find material '{}'".format(printable(mat.getName())))
            except RuntimeError:
                # do not crash if name is ""
                # this is illegal due to OGRE specs, but we want to show that in the UI
                lmgr.logError("sub-mesh uses empty material name")

    def processSkeletonName(self, mesh, name): pass

    def processMeshCompleted(self, mesh): pass

class LogWindow(Ogre.LogListener):
    def __init__(self):
        Ogre.LogListener.__init__(self)

        self.show = False
        self.items = []

        self.font = None
    
    def messageLogged(self, msg, lvl, *args):
        self.items.append((printable(msg.replace("%", "%%")), lvl))

    def draw(self):
        if not self.show:
            return

        ImGui.SetNextWindowSize(ImGui.ImVec2(500, 400), ImGui.ImGuiCond_FirstUseEver)
        self.show = ImGui.Begin("Log", self.show)[1]

        ImGui.PushFont(self.font)
        for msg, lvl in self.items:
            if lvl == 4:
                ImGui.PushStyleColor(ImGui.ImGuiCol_Text, ImGui.ImVec4(1, 0.4, 0.4, 1))
            elif lvl == 3:
                ImGui.PushStyleColor(ImGui.ImGuiCol_Text, ImGui.ImVec4(1, 0.8, 0.4, 1))
            ImGui.TextWrapped(msg)
            if lvl > 2:
                ImGui.PopStyleColor()
        ImGui.PopFont()
        ImGui.End()

class MeshViewerGui(Ogre.RenderTargetListener):

    def __init__(self, app):
        Ogre.RenderTargetListener.__init__(self)
        self.show_about = False
        self.show_metrics = False

        self.app = app

        self.highlighted = -1
        self.orig_mat = None
        self.logwin = app.logwin

    def draw_about(self):
        flags = ImGui.ImGuiWindowFlags_AlwaysAutoResize
        self.show_about = ImGui.Begin("About OgreMeshViewer", self.show_about, flags)[1]
        ImGui.Text("By Pavel Rojtberg")
        ImGui.Text("OgreMeshViewer is licensed under the MIT License, see LICENSE for more information.")
        ImGui.Separator()
        ImGui.BulletText("Ogre:  %s" % Ogre.__version__)
        ImGui.BulletText("ImGui: %s" % ImGui.GetVersion())
        ImGui.End()

    def draw_metrics(self):
        win = self.app.getRenderWindow()
        stats = win.getStatistics()

        ImGui.SetNextWindowPos(ImGui.ImVec2(win.getWidth() - 10, win.getHeight() - 10), ImGui.ImGuiCond_Always, ImGui.ImVec2(1, 1))
        ImGui.SetNextWindowBgAlpha(0.3)
        flags = ImGui.ImGuiWindowFlags_NoMove | ImGui.ImGuiWindowFlags_NoTitleBar | ImGui.ImGuiWindowFlags_NoResize | \
                ImGui.ImGuiWindowFlags_AlwaysAutoResize | ImGui.ImGuiWindowFlags_NoSavedSettings | ImGui.ImGuiWindowFlags_NoFocusOnAppearing | \
                ImGui.ImGuiWindowFlags_NoNav
        self.show_metrics = ImGui.Begin("Metrics", self.show_metrics, flags)[1]
        ImGui.Text("Metrics")
        ImGui.Separator()
        ImGui.Text("Average FPS: {:.2f}".format(stats.avgFPS))
        ImGui.Text("Batches: {}".format(stats.batchCount))
        ImGui.Text("Triangles: {}".format(stats.triangleCount))
        ImGui.End()

    def draw_loading(self):
        win = self.app.getRenderWindow()
        ImGui.SetNextWindowPos(ImGui.ImVec2(win.getWidth() * 0.5, win.getHeight() * 0.5), 0, ImGui.ImVec2(0.5, 0.5))

        flags = ImGui.ImGuiWindowFlags_NoTitleBar | ImGui.ImGuiWindowFlags_NoResize | ImGui.ImGuiWindowFlags_NoSavedSettings
        ImGui.Begin("Loading", True, flags)
        ImGui.Text(self.app.filename)
        ImGui.Separator()
        ImGui.Text("Loading..            ")
        ImGui.End()

    def preRenderTargetUpdate(self, evt):
        if not self.app.cam.getViewport().getOverlaysEnabled():
            return

        Ogre.Overlay.ImGuiOverlay.NewFrame()

        entity = self.app.entity

        if entity is None and self.app.attach_node is None:
            self.draw_loading()
            return

        if ImGui.BeginMainMenuBar():
            if ImGui.BeginMenu("File"):
                if ImGui.MenuItem("Select Renderer"):
                    self.app.getRoot().queueEndRendering()
                    self.app.restart = True
                if ImGui.MenuItem("Save Screenshot", "P"):
                    self.app._save_screenshot()
                if ImGui.MenuItem("Quit", "Esc"):
                    self.app.getRoot().queueEndRendering()
                ImGui.EndMenu()
            if entity is not None and ImGui.BeginMenu("View"):
                enode = entity.getParentSceneNode()
                if ImGui.MenuItem("Show Axes", "A", self.app.axes_visible):
                    self.app._toggle_axes()
                if ImGui.MenuItem("Show Bounding Box", "B", enode.getShowBoundingBox()):
                    self.app._toggle_bbox()
                if entity.hasSkeleton() and ImGui.MenuItem("Show Skeleton", None, entity.getDisplaySkeleton()):
                    entity.setDisplaySkeleton(not entity.getDisplaySkeleton())
                ImGui.EndMenu()

            if ImGui.BeginMenu("Help"):
                if ImGui.MenuItem("Metrics", None, self.show_metrics):
                    self.show_metrics = not self.show_metrics
                if ImGui.MenuItem("Log"):
                    self.logwin.show = True
                if ImGui.MenuItem("About"):
                    self.show_about = True
                ImGui.EndMenu()

            ImGui.EndMainMenuBar()

        if self.show_about:
            self.draw_about()

        if self.show_metrics:
            self.draw_metrics()

        self.logwin.draw()

        if self.app.attach_node is not None:
            # no sidebar yet when loading .scene
            return

        # Mesh Info Sidebar
        mesh = entity.getMesh()

        ImGui.SetNextWindowSize(ImGui.ImVec2(300, ImGui.GetFontSize()*25), ImGui.ImGuiCond_FirstUseEver)
        ImGui.SetNextWindowPos(ImGui.ImVec2(0, ImGui.GetFontSize()*1.5))
        flags = ImGui.ImGuiWindowFlags_NoTitleBar | ImGui.ImGuiWindowFlags_NoMove
        ImGui.Begin("MeshProps", None, flags)
        ImGui.Text(mesh.getName())

        highlight = -1

        if ImGui.CollapsingHeader("Geometry"):
            if mesh.sharedVertexData:
                if ImGui.TreeNode("Shared Vertices: {}".format(mesh.sharedVertexData.vertexCount)):
                    show_vertex_decl(mesh.sharedVertexData.vertexDeclaration)
                    ImGui.TreePop()
            else:
                ImGui.Text("Shared Vertices: None")

            for i, sm in enumerate(mesh.getSubMeshes()):
                submesh_details = ImGui.TreeNode("SubMesh #{}".format(i))
                if ImGui.IsItemHovered():
                    highlight = i

                if submesh_details:
                    ImGui.BulletText("Material: {}".format(printable(sm.getMaterialName())))
                    op = ROP2STR[sm.operationType] if sm.operationType <= 6 else "Control Points"
                    ImGui.BulletText("Operation: {}".format(op))

                    if sm.indexData.indexCount:
                        bits = sm.indexData.indexBuffer.getIndexSize() * 8
                        ImGui.BulletText("Indices: {} ({} bit)".format(sm.indexData.indexCount, bits))
                    else:
                        ImGui.BulletText("Indices: None")

                    if sm.vertexData:
                        if ImGui.TreeNode("Vertices: {}".format(sm.vertexData.vertexCount)):
                            show_vertex_decl(sm.vertexData.vertexDeclaration)
                            ImGui.TreePop()
                    else:
                        ImGui.BulletText("Vertices: shared")
                    ImGui.TreePop()

        if self.highlighted > -1:
            entity.getSubEntities()[self.highlighted].setMaterialName(self.orig_mat)

        if highlight > -1:
            self.orig_mat = printable(entity.getSubEntities()[highlight].getMaterial().getName())
            entity.getSubEntities()[highlight].setMaterial(self.app.highlight_mat)
            self.highlighted = highlight

        animations = entity.getAllAnimationStates()
        if animations is not None and ImGui.CollapsingHeader("Animations"):
            controller_mgr = Ogre.ControllerManager.getSingleton()

            if entity.hasSkeleton():
                ImGui.Text("Skeleton: {}".format(mesh.getSkeletonName()))
                # self.entity.setUpdateBoundingBoxFromSkeleton(True)
            if mesh.hasVertexAnimation():
                ImGui.Text("Vertex Animations")

            for name, astate in animations.getAnimationStates().items():
                if ImGui.TreeNode(name):
                    if astate.getEnabled():
                        if ImGui.Button("Reset"):
                            astate.setEnabled(False)
                            astate.setTimePosition(0)
                            if name in self.app.active_controllers:
                                controller_mgr.destroyController(self.app.active_controllers[name])
                    elif ImGui.Button("Play"):
                        astate.setEnabled(True)
                        self.app.active_controllers[name] = controller_mgr.createFrameTimePassthroughController(
                            Ogre.AnimationStateControllerValue.create(astate, True))
                    changed = False
                    if astate.getLength() > 0:
                        ImGui.SameLine()
                        changed, value = ImGui.SliderFloat("", astate.getTimePosition(), 0, astate.getLength(), "%.3fs")
                    if changed:
                        astate.setEnabled(True)
                        astate.setTimePosition(value)
                    ImGui.TreePop()

        lod_count = mesh.getNumLodLevels()
        if lod_count > 1 and ImGui.CollapsingHeader("LOD levels"):
            entity.setMeshLodBias(1)  # reset LOD override
            strategy = mesh.getLodStrategy().getName()
            curr_idx = entity.getCurrentLodIndex()
            ImGui.Text("Strategy: {}".format(strategy))
            for i in range(lod_count):
                txt = "Base Mesh" if i == 0 else "Level {}: {:.2f}".format(i, mesh.getLodLevel(i).userValue)
                ImGui.Bullet()
                ImGui.Selectable(txt, i == curr_idx)
                if ImGui.IsItemHovered():
                    # force this LOD level
                    entity.setMeshLodBias(1, i, i)

        if ImGui.CollapsingHeader("Bounds"):
            bounds = mesh.getBounds()
            s = bounds.getSize()
            ImGui.BulletText("Size: {:.2f}, {:.2f}, {:.2f}".format(s[0], s[1], s[2]))
            c = bounds.getCenter()
            ImGui.BulletText("Center: {:.2f}, {:.2f}, {:.2f}".format(c[0], c[1], c[2]))
            ImGui.BulletText("Radius: {:.2f}".format(mesh.getBoundingSphereRadius()))

        ImGui.End()

        # ImGui.ShowDemoWindow()

class MeshViewer(OgreBites.ApplicationContext, OgreBites.InputListener):

    def __init__(self, infile, rescfg):
        OgreBites.ApplicationContext.__init__(self, "OgreMeshViewer")
        OgreBites.InputListener.__init__(self)

        self.filename = os.path.basename(infile)
        self.filedir = os.path.dirname(infile)
        self.rescfg = rescfg

        self.entity = None
        self.attach_node = None
        self.highlight_mat = None
        self.restart = False
        self.axes_visible = False

        self.active_controllers = {}

    def keyPressed(self, evt):
        if evt.keysym.sym == OgreBites.SDLK_ESCAPE:
            self.getRoot().queueEndRendering()
        elif evt.keysym.sym == ord("b"):
            self._toggle_bbox()
        elif evt.keysym.sym == ord("a"):
            self._toggle_axes()
        elif evt.keysym.sym == ord("p"):
            self._save_screenshot()

        return True

    def mousePressed(self, evt):
        if evt.clicks != 2:
            return True
        vp = self.cam.getViewport()
        ray = self.cam.getCameraToViewportRay(evt.x / vp.getActualWidth(), evt.y / vp.getActualHeight())
        self.ray_query.setRay(ray)
        for hit in self.ray_query.execute():
            self.camman.setPivotOffset(ray.getPoint(hit.distance))
            break
        return True

    def _toggle_bbox(self):
        if self.attach_node is not None:
            show = self.attach_node.getCreator().getShowBoundingBoxes()
            self.attach_node.getCreator().showBoundingBoxes(not show)
            return

        enode = self.entity.getParentSceneNode()
        enode.showBoundingBox(not enode.getShowBoundingBox())

    def _toggle_axes(self):
        if not self.axes_visible:
            self.scn_mgr.addListener(self.axes)
        else:
            self.scn_mgr.removeListener(self.axes)
        
        self.axes_visible = not self.axes_visible

    def _save_screenshot(self):
        name = os.path.splitext(self.filename)[0]
        outpath = os.path.join(self.filedir, "screenshot_{}_".format(name))

        self.cam.getViewport().setOverlaysEnabled(False)
        self.getRoot().renderOneFrame()
        self.getRenderWindow().writeContentsToTimestampedFile(outpath, ".png")
        self.cam.getViewport().setOverlaysEnabled(True)

    def locateResources(self):
        rgm = Ogre.ResourceGroupManager.getSingleton()
        # ensure our resource group is separate, even with a local resources.cfg
        rgm.createResourceGroup(RGN_MESHVIEWER, False)

        # use parent implementation to locate system-wide RTShaderLib
        OgreBites.ApplicationContext.locateResources(self)

        # allow override by local resources.cfg
        if not self.getFSLayer().fileExists("resources.cfg"):
            # we use the fonts from SdkTrays.zip
            trays_loc = self.getDefaultMediaDir() + "/packs/SdkTrays.zip"
            rgm.addResourceLocation(trays_loc, "Zip", RGN_MESHVIEWER)

        if self.rescfg:
            cfg = Ogre.ConfigFile()
            cfg.loadDirect(self.rescfg)

            for sec, settings in cfg.getSettingsBySection().items():
                for kind, loc in settings.items():
                    rgm.addResourceLocation(loc, kind, sec)

        # explicitly add mesh location to be safe
        if not rgm.resourceLocationExists(self.filedir, Ogre.RGN_DEFAULT):
            rgm.addResourceLocation(self.filedir, "FileSystem", Ogre.RGN_DEFAULT)
        
    def loadResources(self):
        rgm = Ogre.ResourceGroupManager.getSingleton()
        rgm.initialiseResourceGroup(Ogre.RGN_INTERNAL)
        rgm.initialiseResourceGroup(RGN_MESHVIEWER)

        # only capture default group
        self.logwin = LogWindow()
        Ogre.LogManager.getSingleton().getDefaultLog().addListener(self.logwin)
        rgm.initialiseResourceGroup(Ogre.RGN_DEFAULT)

    def setup(self):
        OgreBites.ApplicationContext.setup(self)
        self.addInputListener(self)

        self.restart = False
        imgui_overlay = Ogre.Overlay.ImGuiOverlay()
        ImGui.GetIO().IniFilename = self.getFSLayer().getWritablePath("imgui.ini")

        root = self.getRoot()
        scn_mgr = root.createSceneManager()
        scn_mgr.addRenderQueueListener(self.getOverlaySystem())
        self.scn_mgr = scn_mgr

        # set listener to deal with missing materials
        self.mat_creator = MaterialCreator()
        Ogre.MeshManager.getSingleton().setListener(self.mat_creator)

        # HiDPI
        pixel_ratio = self.getDisplayDPI() / 96
        Ogre.Overlay.OverlayManager.getSingleton().setPixelRatio(pixel_ratio)
        ImGui.GetStyle().ScaleAllSizes(pixel_ratio)

        # for picking
        self.ray_query = scn_mgr.createRayQuery(Ogre.Ray())

        imgui_overlay.addFont("SdkTrays/Value", RGN_MESHVIEWER)
        self.logwin.font = ImGui.GetIO().Fonts.AddFontDefault()
        self.logwin.font.Scale = round(pixel_ratio)

        imgui_overlay.show()
        Ogre.Overlay.OverlayManager.getSingleton().addOverlay(imgui_overlay)
        imgui_overlay.disown()  # owned by OverlayMgr now

        shadergen = OgreRTShader.ShaderGenerator.getSingleton()
        shadergen.addSceneManager(scn_mgr)  # must be done before we do anything with the scene

        scn_mgr.setAmbientLight((.1, .1, .1))

        self.highlight_mat = Ogre.MaterialManager.getSingleton().create("Highlight", RGN_MESHVIEWER)
        self.highlight_mat.getTechniques()[0].getPasses()[0].setEmissive((1, 1, 0))

        main_cam_name = "MeshViewer/Cam"
        self.cam = scn_mgr.createCamera(main_cam_name)
        self.cam.setAutoAspectRatio(True)
        camnode = scn_mgr.getRootSceneNode().createChildSceneNode()
        camnode.attachObject(self.cam)

        vp = self.getRenderWindow().addViewport(self.cam)
        vp.setBackgroundColour((.3, .3, .3))

        self.gui = MeshViewerGui(self)
        self.getRenderWindow().addListener(self.gui)

        self.getRoot().renderOneFrame()
        self.getRoot().renderOneFrame()

        if self.filename.lower().endswith(".scene"):
            self.attach_node = scn_mgr.getRootSceneNode().createChildSceneNode()
            self.attach_node.loadChildren(self.filename)

            self.attach_node._update(True, False)
            diam = self.attach_node._getWorldAABB().getSize().length()

            for c in scn_mgr.getCameras().values():
                if c.getName() == main_cam_name:
                    continue
                # the camera frustum of any contained camera blows the above heuristic
                # so use the camera position instead
                diam = c.getDerivedPosition().length()
                break
        else:
            self.entity = scn_mgr.createEntity(self.filename)
            scn_mgr.getRootSceneNode().createChildSceneNode().attachObject(self.entity)
            diam = self.entity.getBoundingBox().getSize().length()

        self.cam.setNearClipDistance(diam * 0.01)

        self.axes = Ogre.DefaultDebugDrawer()
        self.axes.setStatic(True)
        self.axes.drawAxes(Ogre.Affine3.IDENTITY, diam / 4)

        if len(scn_mgr.getMovableObjects("Light")) == 0:
            # skip creating light, if scene already contains one
            light = scn_mgr.createLight("MainLight")
            light.setType(Ogre.Light.LT_DIRECTIONAL)
            light.setSpecularColour(Ogre.ColourValue.White)
            camnode.attachObject(light)

        self.camman = OgreBites.CameraMan(camnode)
        self.camman.setStyle(OgreBites.CS_ORBIT)
        self.camman.setYawPitchDist(0, 0.3, diam)
        self.camman.setFixedYaw(False)

        self.imgui_input = OgreBites.ImGuiInputListener()
        self.input_dispatcher = OgreBites.InputListenerChain([self.imgui_input, self.camman])
        self.addInputListener(self.input_dispatcher)

    def shutdown(self):
        Ogre.LogManager.getSingleton().getDefaultLog().removeListener(self.logwin)
        OgreBites.ApplicationContext.shutdown(self)

        self.entity = None
        self.axes = None
        if self.restart:
            # make sure empty rendersystem is written
            self.getRoot().shutdown()
            self.getRoot().setRenderSystem(None)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ogre Mesh Viewer")
    parser.add_argument("infile", help="path to a ogre .mesh, ogre .scene or any format supported by assimp")
    parser.add_argument("-c", "--rescfg", help="path to the resources.cfg")
    args = parser.parse_args()
    app = MeshViewer(args.infile, args.rescfg)

    while True:  # allow auto restart
        try:
            app.initApp()
            app.getRoot().startRendering()
            app.closeApp()
        except RuntimeError as e:
            Ogre.LogManager.getSingleton().logMessage(str(e))

        if not app.restart: break
