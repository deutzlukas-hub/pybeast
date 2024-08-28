'''
/**
 * Interface of the Animat class and associated constants.
 * #Inherit this call to create an Animat with a unique control
 * system (overloaded Control method) which you are writing from scratch. If
 * you are working with neural nets you may find it more useful to start with
 * FFNAnimat and DNNAnimat which come with their own neural nets and automatic
 * configuration methods.
 * \author Tom Carden
 * \author David Gordon
 * \see neuralanimat.h
 * \see FFNAnimat
 * \see DNNAnimat
 */
'''
# Built-in
from abc import abstractmethod
import time
from typing import Optional, Dict
import copy
# Third-party
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import gluNewQuadric, gluQuadricDrawStyle, gluDisk, gluDeleteQuadric, GLU_FILL

# Local
from pybeast.core.world.drawable import Drawable
from pybeast.core.world.worldobject import WorldObject
from pybeast.core.utils.colours import random_colour
from pybeast.core.utils.vector2D import Vector2D
from pybeast.core.sensors.sensor import Sensor
from pybeast.core.world.trail import Trail


TWO_PI = 2*np.pi
# Constants
ANIMAT_RADIUS = 5.0		# Animat's default radius.
ANIMAT_MAX_SPEED = 100.0	# Animat's default maximum speed.
ANIMAT_MIN_SPEED = -50.0	# Animat's default minimum speed.
ANIMAT_MAX_ROTATE = 2 * np.pi  # The default max rotation/frame.
ANIMAT_DRAG = 50.0			# An arbitrary friction value.
ANIMAT_ACCEL = 5000.0		# An arbitrary acceleration value.
ANIMAT_TIMESTEP = 0.05		# The default time step.
ANIMAT_PARTS = 4			# The number of different colours.

# Enumeration type for the different coloured parts of the Animat.
class AnimatPartType:
    ANIMAT_BODY = 0
    ANIMAT_CENTRE = 1
    ANIMAT_ARROW = 2
    ANIMAT_WHEEL = 3

ANIMAT_COLOURS = np.zeros((4,4))
ANIMAT_COLOURS[AnimatPartType.ANIMAT_CENTRE][:] = 1.0
ANIMAT_COLOURS[AnimatPartType.ANIMAT_ARROW][:3] = 0.0
ANIMAT_COLOURS[AnimatPartType.ANIMAT_ARROW][3] = 1.0
ANIMAT_COLOURS[AnimatPartType.ANIMAT_WHEEL][0:3] = 0.1
ANIMAT_COLOURS[AnimatPartType.ANIMAT_WHEEL][3] = 1.0


class Animat(WorldObject):

    numAnimats = 0.0

    def __init__(self,
         startLocation: Optional[Vector2D] = None,
         startOrientation: Optional[float] = None,
         startVelocity: Optional[Vector2D] = None,
         minSpeed: float = ANIMAT_MIN_SPEED,
         maxSpeed: float = ANIMAT_MAX_SPEED,
         maxTurn: float = ANIMAT_MAX_ROTATE,
         timeStep: float = ANIMAT_TIMESTEP,
         solid: bool = False,
         randomColour: bool = True,
         interactionRange: float = np.inf,
         controls: Optional[Dict[str, float]] = None):

        super().__init__(
            startLocation,
            startOrientation,
            radius=ANIMAT_RADIUS,
            solid=solid)

        self.startVelocity = startVelocity
        self.minSpeed = minSpeed
        self.maxSpeed = maxSpeed
        self.maxTurn = maxTurn
        self.timeStep = timeStep
        self.randomColour = randomColour
        self.interactionRange = interactionRange

        self.colours = ANIMAT_COLOURS
        self.colours[AnimatPartType.ANIMAT_BODY] = self.GetColour()

        self.distanceTravelled = 0.0
        self.powerUsed = 0.0
        self.sensors = {}
        if controls is None:
            self.controls = {"left": 0.0, "right": 0.0}
        self.trail = Trail()

        if startVelocity is None:
            self.resetRandom['startVelocity'] = True
        else:
            self.resetRandom['startVelocity'] = False

        Animat.numAnimats += 1

    def __del__(self):

        Animat.numAnimats -= 1

        for name, sensor in self.sensors.items():
            if sensor.GetOwner() == self:
                del sensor

        super().__del__()

    def __repr__(self):

        if not self.isInit:
            return self._repr(isInit = self.isInit, startLocation = self.startLocation, startOrientation = self.startOrientation)
        else:
            return self._repr(isInit = self.isInit, location=self.location, orientation=self.orientation,
                velocity=self.radius, colour=self.colour, edges=self.edges)

    def Init(self):

        super().Init()

        # This needs to happen after 'super.Init()' so that random orientation and location have been set
        if self.startVelocity is None:
            self.startVelocity = Vector2D(l=1.0, a=self.orientation)

        self.SetVelocity(self.startVelocity)

        self.InitColour()
        self.trail.SetColour(self.colour[0], self.colour[1], self.colour[2])

        for sensor in self.sensors.values():
            sensor.Init()

        self.isInit = True

        return

    def InitColour(self):

        if self.randomColour:
            Drawable.SetColour(self, *random_colour())

        self.colours[AnimatPartType.ANIMAT_BODY][:] = self.GetColour()
        self.colours[AnimatPartType.ANIMAT_ARROW][:] = self.GetColour()

    def AddSensor(self, name: str, s: Sensor):
        """
        Adds named sensors to the Animat's sensor container and sets the owner to this Animat.

        Parameters:
            name (str): The name of the sensor (unique to the Animat).
            s (Sensor): A pointer to the sensor.

        """

        if name in self.sensors and self.sensors[name].GetOwner() == self:
            del self.sensors[name]

        self.sensors[name] = s
        s.SetOwner(self)

        return

    def Share(self):
        pass

    def Update(self):

        self.Control()

        dt = self.timeStep

        if callable(self.controls["left"]):
            controlLeft = self.controls["left"]()
        elif isinstance(self.controls["left"], float):
            controlLeft = self.controls["left"]
        else:
            assert False

        if callable(self.controls["right"]):
            controlRight = self.controls["right"]()
        elif isinstance(self.controls["right"], float):
            controlRight = self.controls["right"]
        else:
            assert False

        self.OffsetOrientation(self.maxTurn * (controlLeft - controlRight) * dt)

        self.velocity += Vector2D(
            l=(self.maxSpeed - self.minSpeed) * 0.5 * (controlLeft + controlRight) + self.minSpeed,
            a=self.orientation
        )

        # Include "drag force"
        if self.maxSpeed > 0.0:
            self.velocity -= self.velocity * (1.0 / self.maxSpeed) * ANIMAT_DRAG

        if self.velocity.GetLengthSquared() > self.maxSpeed**2:
            self.velocity.SetLength(self.maxSpeed)

        self.OffsetLocation(self.velocity * dt)

        # TODO: Do we really need this?
        # Here we handle wrapping and clear the trail to ensure that no lines are
        # drawn across the display as the Animat zaps from side to side.
        while self.location.x < 0:
            self.SetLocationX(self.location.x + self.myWorld.GetWidth())
            self.trail.Clear()
        while self.location.x >= self.myWorld.GetWidth():
            self.SetLocationX(self.location.x - self.myWorld.GetWidth())
            self.trail.Clear()
        while self.GetLocation().y < 0:
            self.SetLocationY(self.location.y + self.myWorld.GetHeight())
            self.trail.Clear()
        while self.GetLocation().y >= self.GetWorld().GetHeight():
            self.SetLocationY(self.location.y - self.myWorld.GetHeight())
            self.trail.Clear()

        for sensor in self.sensors.values():
            sensor.Update()

        self.distanceTravelled += self.velocity.GetLength() * dt

        for control in self.controls.values():
            self.powerUsed += ((self.maxSpeed - self.minSpeed) * abs(control) + self.minSpeed) * dt

        self.trail.Append(copy.deepcopy(self.GetLocation()))
        self.trail.Update()

        super().Update()

    def Reset(self):
        """
        Reset animat add the end of an assessment
        """
        super().Reset()

        self.distanceTravelled = 0
        self.powerUsed = 0

        if self.resetRandom['startVelocity']:
            self.startVelocity = Vector2D(l=1.0, a=self.orientation)

        self.SetVelocity(self.startVelocity)
        self.trail.Clear()

    @abstractmethod
    def Control(self):
        """
        Needs to overwritten
        """
        pass

    def Interact(self, other):
        """
        Processes collisions with other animats, including rudimentary physics
        (sticky collisions). Also calls onCollide event and sensorInteract on both
        animats.

        :param other: Animat
            A pointer to the Animat we're interacting with.
        """

        if (self.location - other.location).GetLength() <= self.interactionRange:

            # If other object is an Animat
            if isinstance(other, Animat):

                # Sensors go first because we don't want things bouncing away and not be sensed.
                self.SensorInteract(other)

                # TODO: This is not needed because it will be called during Interact(other, self)
                #other.SensorInteract(self)

                # If objects are touching and are solid we handle their collision
                # TODO: Added 'and self.isSolid()' because it makes more sense
                if self.IsTouching(other):
                    if self.IsSolid() and other.IsSolid():
                        averageVelocity = (self.velocity + other.velocity) * 0.5
                        vecToOther = other.location - self.location
                        minDistance = self.radius + other.radius

                        self.SetVelocity(averageVelocity)
                        other.SetVelocity(averageVelocity)

                        # Offsetting location: After this object are not touching anymore
                        self.OffsetLocation(vecToOther.GetReciprocal().GetNormalized() * (minDistance - vecToOther.GetLength()))
                        other.OffsetLocation(vecToOther.GetNormalized() * (minDistance - vecToOther.GetLength()))

                    # Can be implemented to trigger additional actions during collision
                    self.OnCollision(other)
                    other.OnCollision(self)
                    # Add collision point to world.Collision (collisions are invisible by default)
                    self.myWorld.AddCollision(self.collisionPoint)

                # If other object is not an animat
            else:
                if self.myWorld.mySimulation.profile:
                    startTime = time.time()
                    self.myWorld.mySimulation.profiler.functionsToProfile['animat.Interact.withObjects.Sensor.Interact']['count'] += 1

                # Sensor's animats interact with others
                self.SensorInteract(other)

                if self.myWorld.mySimulation.profile:
                    endTime = time.time()
                    self.myWorld.mySimulation.profiler.functionsToProfile[
                        'animat.Interact.withObjects.Sensor.Interact']['times'].append(endTime - startTime)

                if self.myWorld.mySimulation.profile:
                    startTime = time.time()
                    self.myWorld.mySimulation.profiler.functionsToProfile[
                        'animat.Interact.withObjects.Collision']['count'] += 1

                if self.IsTouching(other):
                    if self.IsSolid() and other.IsSolid():
                        self.OffsetLocation(self.collisionNormal * (self.GetRadius() - (self.GetLocation() - self.collisionPoint).GetLength()))

                    # Can be implemented to trigger additional actions during collision
                    self.OnCollision(other)
                    other.OnCollision(self)
                    # Add collision point to world.Collision (collisions are invisible by default)
                    self.myWorld.AddCollision(self.collisionPoint)

                if self.myWorld.mySimulation.profile:
                    endTime = time.time()
                    self.myWorld.mySimulation.profiler.functionsToProfile[
                        'animat.Interact.withObjects.Collision']['times'].append(endTime - startTime)

        # Can be implemented
        super().Interact(other)

    def IsTouching(self, other):
        vecToOther = other.GetLocation() - self.GetLocation()
        minDistance = self.GetRadius() + other.GetRadius()

        if vecToOther.GetLengthSquared() > minDistance * minDistance:
            return False

        self.collisionPoint, self.collisionNormal = other.GetNearestPoint(self.GetLocation())

        return other.IsCircular() or self.IsInside(self.collisionPoint)

    def OnCollision(self, other):
        # TODO: Does this should have an other argument
        pass

    def SensorInteract(self, other):
        for sensor in self.sensors.values():
            sensor.Interact(other)

    def Display(self):

        if (self.GetWorld().GetDispConfig() & self.myWorld.worldDisplayType.DISPLAY_SENSORS) != 0:
            for sensor in self.sensors.values():
                sensor.Display()

        if (self.GetWorld().GetDispConfig() & self.myWorld.worldDisplayType.DISPLAY_TRAILS) != 0:
            self.trail.Display()

        if self.GetWorld().GetDispConfig():
            super().Display()

    def Draw(self) -> None:

        colTemp = self.GetColour()
        Drawable.SetColour(self, *self.colours[AnimatPartType.ANIMAT_BODY].tolist())
        Drawable.Draw(self)  # Borrow the nice shaded effect from drawable
        Drawable.SetColour(self, *colTemp)

        # Animat centre
        glColor4fv(self.colours[AnimatPartType.ANIMAT_CENTRE].tolist())
        Disk = gluNewQuadric()
        gluQuadricDrawStyle(Disk, GLU_FILL)
        gluDisk(Disk, 0, (self.GetRadius() / 0.85) - 4.0, 20, 1)  # body
        gluDeleteQuadric(Disk)

        # Direction arrow
        glColor4fv(self.colours[AnimatPartType.ANIMAT_ARROW])
        glLineWidth(1.0)
        glBegin(GL_LINE_STRIP)
        glVertex2d(0.0, self.GetRadius() / 2.0)
        glVertex2d(self.GetRadius() / 1.5, 0.0)
        glVertex2d(0.0, self.GetRadius() / -2.0)
        glEnd()

        # Right wheel
        glColor4fv(self.colours[AnimatPartType.ANIMAT_WHEEL])
        glLineWidth(4.0)
        glBegin(GL_LINE_STRIP)
        glVertex2d(self.GetRadius() / -2.0, 2.0 - self.GetRadius())
        glVertex2d(self.GetRadius() / 2.0, 2.0 - self.GetRadius())
        glEnd()

        # Left wheel
        glColor4fv(self.colours[AnimatPartType.ANIMAT_WHEEL])
        glLineWidth(4.0)
        glBegin(GL_LINE_STRIP)
        glVertex2d(self.GetRadius() / -2.0, self.GetRadius() - 2.0)
        glVertex2d(self.GetRadius() / 2.0, self.GetRadius() - 2.0)
        glEnd()

    #------------------------------------------------------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------------------------------------------------------
    def GetVelocity(self):
        return self.velocity

    def GetMaxSpeed(self):
        return self.maxSpeed

    def GetMinSpeed(self):
        return self.minSpeed

    def GetMaxRotateSpeed(self):
        return self.maxTurn

    @staticmethod
    def GetNumAnimats():
        return Animat.numAnimats

    def GetTimeStep(self):
        return self.timeStep

    def GetDistanceTravelled(self):
        return self.distanceTravelled

    def GetPowerUsed(self):
        return self.powerUsed

    def GetSensors(self):
        return self.sensors

    def GetControls(self):
        return self.controls

    # ------------------------------------------------------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------------------------------------------------------
    def SetStartLocation(self, l: Vector2D):
        self.startLocation = l

    def SetStartOrientation(self, o: float):
        self.startOrientation = o

    def SetTimeStep(self, t: float):
        self.timeStep = t

    def SetCollisionPoint(self, v: Vector2D):
        self.collisionPoint = v

    def SetCollisionNormal(self, v: Vector2D):
        self.collisionNormal = v

    def SetInteractionRange(self, r: float):
        self.interactionRange = r

    def SetVelocity(self, pv: Vector2D):
        self.velocity = pv

    def SetVelocityX(self, x: float):
        self.velocity.x = x

    def SetVelocityY(self, y: float):
        self.velocity.y = y

    def AddVelocity(self, v: Vector2D):
        self.velocity + v

    def SetMaxSpeed(self, s: float):
        assert isinstance(s, float)
        self.maxSpeed = s

    def SetMinSpeed(self, s: float):
        assert isinstance(s, float)
        self.minSpeed = s

    def SetMaxRotationSpeed(self, s: float):
        assert isinstance(s, float)
        self.maxTurn = s

    def SetColour(self,
        part: int,
        col: Optional[list] = None,
        r: float = 0.0,
        g: float = 0.0,
        b: float = 0.0,
        a: float = 1.0):

        if col is not None:
            self.colours[part][:] = col
        else:
            self.colours[part][0] = r
            self.colours[part][1] = g
            self.colours[part][2] = b
            self.colours[part][3] = a
        return

    def Serialise(self, out):
        # TODO: Make this pytonic
        out.write("Animat\n")
        super(WorldObject, self).Serialise(out)  # Assuming WorldObject has a Serialise method
        out.write(str(self.controls) + "\n")
        out.write(str(self.velocity) + "\n")
        out.write(str(self.maxSpeed) + "\n")
        out.write(str(self.minSpeed) + "\n")
        out.write(str(self.maxTurn) + "\n")
        out.write(str(self.startLocation) + "\n")
        out.write(str(self.startOrientation) + "\n")
        out.write(str(self.distanceTravelled) + "\n")
        out.write(str(self.powerUsed) + "\n")

    def Unserialise(self, stream):
        # TODO: Make this pytonic
        pass
