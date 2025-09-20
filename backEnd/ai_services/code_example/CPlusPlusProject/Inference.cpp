#include "teAiFlowEngine.h"
#include <iostream>
#include <fstream>
#include <Windows.h>
#include "nlohmann/json.hpp"

using json = nlohmann::json;

namespace nlohmann {
    template <>
    struct adl_serializer<TePoint2f> {
        static void to_json(json& j, const TePoint2f& p) {
            j = json{ {"x", p.fX}, {"y", p.fY} };
        }

        static void from_json(const json& j, TePoint2f& p) {
            j.at("x").get_to(p.fX);
            j.at("y").get_to(p.fY);
        }
    };
}

std::string extractFileName(const std::string& path) {
    size_t found = path.find_last_of("/\\");
    if (found != std::string::npos) {
        return path.substr(found + 1);
    }
    return path;
}

std::string extractFileNameWithoutExtension(const std::string& path) {
    size_t found = path.find_last_of("/\\");
    if (found != std::string::npos) {
        std::string fileName = path.substr(found + 1);
        size_t dotPos = fileName.find_last_of('.');
        if (dotPos != std::string::npos) {
            return fileName.substr(0, dotPos);
        }
        return fileName;
    }
    return path;
}

static std::string GBKTOUTF8(const std::string& strGBK)
{
    std::string strUtf8;
    int len = MultiByteToWideChar(CP_ACP, 0, strGBK.c_str(), -1, NULL, 0);
    wchar_t* wszUtf8 = new wchar_t[len];
    memset(wszUtf8, 0, len);
    MultiByteToWideChar(CP_ACP, 0, strGBK.c_str(), -1, wszUtf8, len);
    len = WideCharToMultiByte(CP_UTF8, 0, wszUtf8, -1, NULL, 0, NULL, NULL);
    char* szUtf8 = new char[len + 1];
    memset(szUtf8, 0, len + 1);
    WideCharToMultiByte(CP_UTF8, 0, wszUtf8, -1, szUtf8, len, NULL, NULL);
    strUtf8 = szUtf8;
    delete[] szUtf8;
    delete[] wszUtf8;
    return strUtf8;
}


int processAiNode(std::string projDir,std::string picDir)
{
    TeAiFlowEngine engine;
    bool ret = engine.loadProj(projDir);
    if (ret) {
        std::cout << "Load Solution Success" << std::endl;
    }
    else {
        std::cout << engine.getLastError() << std::endl;
        return 0;
    }

#if 0
    {

        std::vector<std::string> vNodes = engine.getNodeList();

        std::vector<std::string> vAiNodes;
        for (std::string& nodeName : vNodes)
        {
            std::string nodeType = engine.getNodeType(nodeName);

            std::cout << nodeName << "--Type : " << nodeType << std::endl;

            if (nodeType == "Location" || nodeType == "Detection" || nodeType == "Classify" ||
                nodeType == "PixelDetect" || nodeType == "Unsupervised" || nodeType == "AngleRegress")
            {
                vAiNodes.push_back(nodeName);
            }
        }

        TeProjGraphExecPath execPath = engine.getProjGraphExecPath("图像源");
        for (const std::pair<TeNodeFlowPair, std::set<TeNodeFlowPair>>& nodePair : execPath)
        {
            std::cout << "Node : " << nodePair.first.first << ", Flow : " << nodePair.first.second << std::endl;
            for (const TeNodeFlowPair& nextNode : nodePair.second)
            {
                std::cout << " --Next Node : " << nextNode.first << ", Flow : " << nextNode.second << std::endl;
            }
        }


        for (std::string& nodeName : vNodes) {
            std::vector<std::string> nodeFLows = engine.getNodeFlows(nodeName);
        }


        for (std::string& nodeName : vAiNodes) {
            std::cout << "NodeName: " << nodeName << std::endl;
            std::vector<std::string> markNames;
            engine.getAiNodeMarkName(nodeName, &markNames);
            for (std::string& markName : markNames)
            {
                std::cout << "  --" << markName << std::endl;
            }
        }
    }
 #endif
    ret = engine.addInputImageNode("图像源", 10000, 10000, 1);
    if (ret) {
        std::cout << "addInputImageNode Success" << std::endl;
    }
    else {
        std::cout << engine.getLastError() << std::endl;
        return 0;
    }

    ret = engine.addAiNodeOutput("PixelDetect2", "defaultFlow");
    if (ret) {
        std::cout << "addOutput Success" << std::endl;
    }
    else {
        std::cout << engine.getLastError() << std::endl;
        return 0;
    }
    engine.setOutputBufferEnable(true);

    ret = engine.initExec();
    if (ret) {
        std::cout << "Proj Init Success!" << std::endl;
    }
    else {
        std::cout << engine.getLastError() << std::endl;
        return 0;
    }

    teAiFlowEngine_StartWarmupGpu({ 0 }, 100);
    ret = engine.startExec();
    if (ret) {
        std::cout << "Proj Start Exec!" << std::endl;
    }
    else {
        std::cout << engine.getLastError() << std::endl;
        return 0;
    }

    std::vector<std::string> imgFiles = getAllFiles(picDir, ".bmp");

    std::string outdir = "out";
    json allInstancesJson = json::array();

    for (size_t i = 0; i < imgFiles.size(); i++) {
        TeImage image = loadImage(imgFiles[i]);

        ret = engine.pushData("图像源", image);
        if (!ret) {
            std::cout << engine.getLastError() << std::endl;
            break;
        }

        std::vector<AiInstance> instances;
        ret = engine.getAiNodeOutput("PixelDetect2", "defaultFlow", &instances);
        std::cout << "==========================(" << i << ":" << imgFiles[i] << ")==========================" << std::endl;

        std::cout << "instances size:" << instances.size() << std::endl;

        json currentImageJson;
        currentImageJson["imageFile"] = GBKTOUTF8(extractFileName(imgFiles[i]));
        currentImageJson["instances"] = json::array();

        for (const auto& instance : instances) {
            json instanceJson;
            instanceJson["strName"] = GBKTOUTF8(instance.strName);
            instanceJson["outerContour"] = instance.outerContour();
            currentImageJson["instances"].push_back(instanceJson);
            std::cout << "strName:"<< instance.strName << std::endl;
        }

        allInstancesJson.push_back(currentImageJson);

        TeImage drawImg = image.clone();
        drawAiInstanceConnectedRegion(drawImg, instances, 0, 255, 0);

        std::string outFile = outdir + "/" + extractFileNameWithoutExtension(imgFiles[i]) + "_out.png";
        saveImage(outFile, drawImg);
    }

    std::ofstream  file("output.json");
    if (file.is_open()) {
        file << std::setw(4) << allInstancesJson << std::endl;
        file.close();
        std::cout << "JSON data has been written to file." << std::endl;
    }
    else {
        std::cerr << "Failed to open file for writing." << std::endl;
    }

    ret = engine.stopExec();
    ret = engine.releaseExec();

    return 0;

}



int main(int argc, char** argv)
{
    if (argc <3) {
        std::cout << "argc=" << argc << std::endl;
        std::cout <<"参数出错，输入以下命令：CPlusPlusProject.exe proj文件路径   推理的图片路径"<< std::endl;
        return 0;
    }
    for (int i = 0; i < argc; i++) {
        printf("[%d]:%s\n",i,argv[i]);
    }
    std::string projectDir = std::string(argv[1]);
    std::cout << "proj文件路径:" << projectDir << std::endl;
    std::string picDir = std::string(argv[2]);
    std::cout << "图片路径:" << picDir << std::endl;
   processAiNode(projectDir,picDir);

    //processCrop();
    return 1;
}



