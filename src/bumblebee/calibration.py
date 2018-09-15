import numpy as np
from sensor_msgs.msg import CameraInfo,RegionOfInterest
###
#single location for all standard required classes and data structures

import rospy
import sys
import os
import cv2

import scipy.stats.mstats as stat

import matplotlib.pyplot as plt

import pickle


def drawROI(leftROI,rightROI,overlapROI,imgSize=(1024,768)):
    cameraImage=np.zeros((imgSize[1],imgSize[0],3), np.int8)
    overlapImage=np.zeros((imgSize[1],imgSize[0],3), np.int8)

    cv2.rectangle(cameraImage, (leftROI[1],leftROI[0]),
                   (leftROI[1]+leftROI[3],leftROI[0]+leftROI[2]),(0,0,255),10)
    cv2.rectangle(cameraImage, (rightROI[1],rightROI[0]),
                   (rightROI[1]+rightROI[3],rightROI[0]+rightROI[2]),(255,0,0),10)
    cv2.rectangle(overlapImage, (overlapROI[1],overlapROI[0]),
                   (overlapROI[1]+overlapROI[3],overlapROI[0]+overlapROI[2]),(0,255,0),-1)
    overallImage=cv2.addWeighted(cameraImage, 0.7, overlapImage, 0.2, 0)


    cv2.imwrite("/home/ryan/CALIMAGE.ppm",overallImage)
    return overallImage

def getROIoverlap(leftROI,rightROI):
    ###y,x,height,width
    print(leftROI,rightROI)
    x=max(leftROI[0],rightROI[0])
    y=max(leftROI[1],rightROI[1])
    w=min(leftROI[0]+leftROI[2],rightROI[0]+rightROI[2])-x
    h=min(leftROI[1]+leftROI[3],rightROI[1]+rightROI[3])-y
    #x = min(a[0], b[0])
    #y = min(a[1], b[1])
    #w = max(a[0] + a[2], b[0] + b[2]) - x
    #h = max(a[1] + a[3], b[1] + b[3]) - y
    return (x, y, w, h)

class RectificationInfo():
    def __init__(self):
        self.intXMapping=None
        self.intYMapping=None
        self.floatXMapping=None
        self.floatYMapping=None
    def getRectifiedImage(self,inImage,isFloat=True):
        if(isFloat):
            return cv2.remap(inImage,self.floatXMapping,self.floatYMapping,cv2.INTER_LINEAR)
        else:
            return cv2.remap(inImage, self.intXMapping, self.intYMapping, cv2.INTER_LINEAR)



class calibrationMetaData():
    def __init__(self,vArgs):
        self.inDirectory=vArgs[0]
        self.outDirectory=vArgs[1]
        self.squareWidth=float(vArgs[2])
        self.nWidth=int(vArgs[3])
        self.nHeight=int(vArgs[4])
        self.distortionModel=vArgs[5]
        self.debayer=bool(vArgs[6])
        self.imgSize=(0,0)
    def printSettings(self):
        print("Settings:")
        print(self.inDirectory)
        print(self.outDirectory)
        print(self.squareWidth)
        print(self.nWidth)
        print(self.nHeight)
        print(self.debayer)
        print(self.distortionModel)
    def getBoardSize(self):
        return (self.nWidth - 1,self.nHeight-1)
class SingleCameraCalData():
    def __init__(self):
        self.Lparam=SingleCameraParamData()
        self.Rparam=SingleCameraParamData()
        self.meta=None
        self.LeftPoints=[]
        self.LeftReprojected = []
        self.PatternPoints=[]##the coordinates of each point relative to the checkerboard (0,0,0),(squareSize.0,0)....
        self.LT=[]
        self.LR=[]
        self.RR=[]
        self.RT=[]
        self.RightPoints=[]
        self.RightReprojected=[]
        self.imgName=[]
    def getRMSreprojection(self):
        avgErrorLeft=0
        avgErrorRight=0
        avgTogether=0
        count=0
        for imageIndex in range(len(self.LeftPoints)):
            for ptIndex in range(len(self.LeftPoints[imageIndex])):
                avgErrorLeft+=np.square(self.LeftPoints[imageIndex][ptIndex]-self.LeftReprojected[imageIndex][ptIndex]).sum()
        for imageIndex in range(len(self.RightPoints)):
            for ptIndex in range(len(self.RightPoints[imageIndex])):
                avgErrorRight+=np.square(self.RightPoints[imageIndex][ptIndex]-self.RightReprojected[imageIndex][ptIndex]).sum()
        for imageIndex in range(len(self.LeftPoints)):
            for ptIndex in range(len(self.LeftPoints[imageIndex])):
                avgTogether+=(np.square(self.LeftPoints[imageIndex][ptIndex]-self.LeftReprojected[imageIndex][ptIndex]).sum()+np.square(self.RightPoints[imageIndex][ptIndex]-self.RightReprojected[imageIndex][ptIndex]).sum()).sum()
        npoints=len(self.LeftPoints)*len(self.LeftPoints[0])
        return [np.sqrt(avgErrorLeft/npoints),np.sqrt(avgErrorRight/npoints),np.sqrt(avgTogether/npoints)/1000]
    def getSingleImageRMS(self,imgIndex):
        leftImageRMS=0
        rightImageRMS=0
        for ptIndex in range(len(self.LeftPoints[imgIndex])):
            rightImageRMS += np.square(self.RightPoints[imgIndex][ptIndex] - self.RightReprojected[imgIndex][ptIndex]).sum()
            leftImageRMS += np.square(self.LeftPoints[imgIndex][ptIndex] - self.LeftReprojected[imgIndex][ptIndex]).sum()
        return [np.sqrt(leftImageRMS/len(self.LeftPoints[imgIndex])),np.sqrt(rightImageRMS/len(self.RightPoints[imgIndex])),np.sqrt((leftImageRMS+rightImageRMS)/2*len(self.LeftPoints[imgIndex]))/100]
    def showImageCoverage(self):
        leftImage = 255*np.ones((self.meta.imgSize[0],self.meta.imgSize[1], 3), np.uint8)
        rightImage = 255*np.ones((self.meta.imgSize[0],self.meta.imgSize[1], 3), np.uint8)
        for imgIndex in self.LeftPoints:
            cv2.drawChessboardCorners(leftImage, (self.meta.nWidth - 1,
                                                  self.meta.nHeight - 1),
                                      imgIndex, True)
        for imgIndex in self.RightPoints:
            cv2.drawChessboardCorners(rightImage, (self.meta.nWidth - 1,
                                                  self.meta.nHeight - 1),
                                      imgIndex, True)
        return [leftImage,rightImage]
class SingleCameraParamData():
    def __init__(self):
        self.K=None
        self.D=None
        self.RMS_error=0
        self.calibrationFlags=0
    def p(self):
        print("K",self.K)
        print("D",self.D)
        print("RMS",self.RMS_error)

class StereoCameraCalData():
    def __init__(self):
        self.calibrationFlags=0
        self.RMS_error=0
        self.lRect=RectificationInfo()
        self.rRect=RectificationInfo()
        self.optimizedLeft=SingleCameraParamData()
        self.optimizedRight=SingleCameraParamData()




class StereoCameraInfo():
    def __init__(self):
        self.RMS=0
        self.calibrationFlags=0
        self.inCalibrationData=SingleCameraCalData()
        self.lRect = RectificationInfo()
        self.rRect = RectificationInfo()
        self.extrin=StereoExtrinsicInfo()
        self.intrin=StereoIntrinsicInfo()
    def calibrateFromFile(self,SingleCameraDirectory):
        self.inCalibrationData = pickle.load(open(SingleCameraDirectory, "rb"))
        self.calibrationFlags=self.inCalibrationData.Lparam.calibrationFlags+cv2.CALIB_USE_INTRINSIC_GUESS + cv2.CALIB_SAME_FOCAL_LENGTH

        (self.RMS,
         self.intrin.optimizedLeft.K,self.intrin.optimizedLeft.D,
         self.intrin.optimizedRight.K,self.intrin.optimizedRight.D,
         self.extrin.R,self.extrin.T,
         self.extrin.E,self.extrin.F)=cv2.stereoCalibrate(self.inCalibrationData.PatternPoints,
                                                          self.inCalibrationData.LeftPoints,self.inCalibrationData.RightPoints,
                                                          self.inCalibrationData.Lparam.K,self.inCalibrationData.Lparam.D,
                                                          self.inCalibrationData.Rparam.K,self.inCalibrationData.Rparam.D,
                                                          self.inCalibrationData.meta.imgSize,flags=self.calibrationFlags,
                                                          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 1000, 0.1))
        print(self.RMS)
        #print(cv2.stereoRectify.__doc__)
        (self.extrin.Rleft,self.extrin.Rright,
         self.intrin.Pl,self.intrin.Pr,self.intrin.Q,
         self.intrin.lROI,self.intrin.rROI)=cv2.stereoRectify(self.intrin.optimizedLeft.K,self.intrin.optimizedLeft.D,
                                                              self.intrin.optimizedRight.K,self.intrin.optimizedRight.D,
                                                              self.inCalibrationData.meta.imgSize,self.extrin.R,self.extrin.T,
                                                              alpha=-1)
        print(self.intrin.lROI,self.intrin.rROI)


        ##mapping arguments
        print("initializing remapping Arguments")
        #print(cv2.initUndistortRectifyMap.__doc__)
        flippedSize=(self.inCalibrationData.meta.imgSize[1],self.inCalibrationData.meta.imgSize[0])
        ###not sure why it needs to be flipped, but the mapping size is opposite to the image size
        self.lRect.floatXMapping,self.lRect.floatYMapping=cv2.initUndistortRectifyMap(self.intrin.optimizedLeft.K,
                                                                                      self.intrin.optimizedLeft.D,
                                                                                      self.extrin.Rleft,
                                                                                      self.intrin.optimizedLeft.K[0:3,0:3],
                                                                                      size=flippedSize,
                                                                                      m1type=cv2.CV_32F)
        self.lRect.intXMapping,self.lRect.intYMapping=cv2.initUndistortRectifyMap(self.intrin.optimizedLeft.K,
                                                                                      self.intrin.optimizedLeft.D,
                                                                                      self.extrin.Rleft,
                                                                                      self.intrin.optimizedLeft.K[0:3,0:3],
                                                                                      size=flippedSize,
                                                                                      m1type=cv2.CV_16SC2)
        self.rRect.floatXMapping,self.rRect.floatYMapping=cv2.initUndistortRectifyMap(self.intrin.optimizedRight.K,
                                                                                      self.intrin.optimizedRight.D,
                                                                                      self.extrin.Rright,
                                                                                      self.intrin.optimizedRight.K[0:3,0:3],
                                                                                      size=flippedSize,
                                                                                      m1type=cv2.CV_32F)
        self.rRect.intXMapping,self.rRect.intYMapping=cv2.initUndistortRectifyMap(self.intrin.optimizedRight.K,
                                                                                      self.intrin.optimizedRight.D,
                                                                                      self.extrin.Rright,
                                                                                      self.intrin.optimizedRight.K[0:3,0:3],
                                                                                      size=flippedSize,
                                                                                      m1type=cv2.CV_16SC2)
        print("completed calibration estimation")
    def getReprojections(self):
        ##estimate all the checkerboard pattern rotations
        LeftProjections=[]
        RightProjections=[]
        lTvec = []
        lRvec = []
        rTvec = []
        rRvec = []
        print(cv2.solvePnP.__doc__)
        for imgIndex in range(len(self.inCalibrationData.PatternPoints)):
            found, r, t = cv2.solvePnP(np.array(self.inCalibrationData.PatternPoints[imgIndex]),
                                         np.array(self.inCalibrationData.LeftPoints[imgIndex]),
                                         np.array(self.intrin.optimizedLeft.K),
                                         np.array(self.intrin.optimizedLeft.D))
            lRvec.append(r)
            lTvec.append(t)

            r, t, inliers = cv2.solvePnP(np.array(self.inCalibrationData.PatternPoints[imgIndex]),
                                         np.array(self.inCalibrationData.RightPoints[imgIndex]),
                                         np.array(self.intrin.optimizedLeft.K),
                                         np.array(self.intrin.optimizedLeft.D))
            rRvec.append(r)
            rTvec.append(t)
        #estimate the reprojections
        for imgIndex in range(len(self.inCalibrationData.PatternPoints)):
            imgReprojected = []
            for PtsIdx in np.array(self.inCalibrationData.PatternPoints[imgIndex]):
                reprojected, jacob = cv2.projectPoints(PtsIdx.reshape((1, 3)),
                                                       np.array(lRvec[imgIndex]),
                                                       np.array(lTvec[imgIndex]),
                                                       self.intrin.optimizedLeft.K, self.intrin.optimizedLeft.D)
                imgReprojected.append(reprojected)
                # totalError+=np.square(reprojected-LeftCorners[imgIdx][count]).sum()
                # otherError+=np.linalg.norm(reprojected-LeftCorners[imgIdx][count])**2
                # avgEuclidian.append(np.linalg.norm(reprojected-LeftCorners[imgIdx][count]))
            LeftProjections.append(imgReprojected)
        return [LeftProjections,RightProjections]



class StereoExtrinsicInfo():
    def __init__(self):
        self.E = np.zeros((3, 3), np.float64)
        self.F = np.zeros((3, 3), np.float64)
        self.R = np.identity(3, np.float64)
        self.T = np.zeros((3, 1), np.float64)
        self.Rleft=np.identity(3,np.float64)
        self.Rright=np.identity(3,np.float64)
    def getBaseline(self):
        print("R",self.R)
        rMatrix=np.zeros(shape=(3,3))
        cv2.Rodrigues(self.R,rMatrix)
        return [self.T,rMatrix]
    def getTransformChain(self):
        leftFrame=np.identity(4,np.float64)
        rightFrame=np.zeros((4,4),np.float64)

        rightFrame[0:3,0:3]=self.R
        rightFrame[0,3]=self.T[0,0]
        rightFrame[1,3]=self.T[1,0]
        rightFrame[2,3]=self.T[2,0]
        rightFrame[3,3]=1


        leftRectifiedFrame=np.zeros((4,4),np.float64)
        leftRectifiedFrame[0:3,0:3]=self.Rleft
        leftRectifiedFrame[3,3]=1

        rightRectifiedFrame=np.zeros((4,4),np.float64)
        rightRectifiedFrame[0:3,0:3]=self.Rright
        rightRectifiedFrame[3,3]=1

        return [leftFrame,rightFrame,leftRectifiedFrame,rightRectifiedFrame]
    def getIdealBaseline(self):
        #L---->lR
        #\
        #\R----->rR
        transform=self.getTransformChain()
        combinedTransform=np.dot(np.linalg.inv(transform[2]),transform[0])
        combinedTransform=np.dot(combinedTransform,transform[1])
        combinedTransform=np.dot(combinedTransform,transform[3])
        return combinedTransform
    def p(self):
        print("Extrinsic---")
        print("E",self.E)
        print("F",self.F)
        print("R",self.R)
        print("T",self.T)
        print("Rleft",self.Rleft)
        print("Rright",self.Rright)
        print("Ideal")
        print(self.getIdealBaseline())
        print("Baseline")
        print(self.getBaseline())


class StereoIntrinsicInfo():
    def __init__(self):
        self.optimizedLeft=SingleCameraParamData()
        self.optimizedRight=SingleCameraParamData()
        self.Pl=np.zeros((3,4),np.float64)
        self.lROI=((0,0),(0,0))
        self.Pr=np.zeros((3,4),np.float64)
        self.rROI = ((0, 0), (0, 0))
        self.Q=np.zeros((4,4),np.float64)
    def p(self):
        print("StereoIntrinsicInfo")
        print("left-----")
        print("Pl",self.Pl)
        print("lROI",self.lROI)
        self.optimizedLeft.p()
        print("right----")
        print("Pr",self.Pr)
        print("rROI",self.rROI)
        self.optimizedRight.p()
        print("Q",self.Q)