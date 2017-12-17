#include <bumblebee/configurationManager.hpp>

configurationManager::configurationManager(std::string stereoInputFile)
{

	cv::FileStorage in(stereoInputFile,cv::FileStorage::READ);
	in["StereoRect"]>>bumblebee;
	in.release();
	ROS_INFO_STREAM("stereo File Loaded from :"<<stereoInputFile);
	///setup services
	
	getRectificationMapServ=n.advertiseService("bumblebee_configuration/getRectificationMap",&configurationManager::RectificationMap,this);
	getOffsetServ=n.advertiseService("bumblebee_configuration/getOffset",&configurationManager::Offset,this);
	
	
}


bool configurationManager::RectificationMap(bumblebee::getRectificationMap::Request& req, bumblebee::getRectificationMap::Response& res)
{
	if(req.floatingPoint)
	{
		cv_bridge::CvImage(std_msgs::Header(),"32FC1",bumblebee.L_fMapx_).toImageMsg(res.leftx);
		cv_bridge::CvImage(std_msgs::Header(),"32FC1",bumblebee.L_fMapy_).toImageMsg(res.lefty);
		cv_bridge::CvImage(std_msgs::Header(),"32FC1",bumblebee.R_fMapx_).toImageMsg(res.rightx);
		cv_bridge::CvImage(std_msgs::Header(),"32FC1",bumblebee.R_fMapy_).toImageMsg(res.righty);
	}
	else
	{
		cv_bridge::CvImage(std_msgs::Header(),"16SC2",bumblebee.L_iMapx_).toImageMsg(res.leftx);
		cv_bridge::CvImage(std_msgs::Header(),"16SC2",bumblebee.L_iMapy_).toImageMsg(res.lefty);
		cv_bridge::CvImage(std_msgs::Header(),"16SC2",bumblebee.R_iMapx_).toImageMsg(res.rightx);
		cv_bridge::CvImage(std_msgs::Header(),"16SC2",bumblebee.R_iMapy_).toImageMsg(res.righty);
	}
	
	return true;
}



bool configurationManager::Offset(bumblebee::getOffset::Request& req, bumblebee::getOffset::Response& res)
{
	res.left.x_offset=bumblebee.l_ROI_.x;
	res.left.y_offset=bumblebee.l_ROI_.y;
	res.left.height=bumblebee.l_ROI_.height;
	res.left.width=bumblebee.l_ROI_.width;

	res.right.x_offset=bumblebee.r_ROI_.x;
	res.right.y_offset=bumblebee.r_ROI_.y;
	res.right.height=bumblebee.r_ROI_.height;
	res.right.width=bumblebee.r_ROI_.width;
	return true;
}