# scientific-plot-digitizer
Codex skill for digitizing scientific plot images into smooth CSV/Excel data with axis calibration, QA replots, and broken-axis notes. 科研曲线图片数据提取 Codex skill，支持坐标标定、平滑数据导出、复绘检查与断轴说明。

中文
Scientific Plot Digitizer 是一个用于科研曲线图片数据提取的 Codex skill，适用于论文图片、截图、断轴图、扫描图中的曲线数据反推。
它可以从应力-时间曲线、光谱曲线、剂量响应曲线、衰减曲线、保持率曲线等 XY 科研图中提取近似数值，并生成平滑的 CSV/Excel 数据。

功能
基于坐标轴刻度进行标定
支持曲线、散点和简单柱状图的数据提取流程
使用单调平滑插值重建曲线
导出 CSV 和 Excel
生成复绘图用于检查提取效果
支持断轴图和隐藏坐标区说明
适合论文图、学位论文图和已发表文献图的数据反推

重要说明
图片提取的数据是基于像素重建的近似值，不等同于原始实验数据。如果能获得原始 CSV、Excel 或绘图源文件，应优先使用原始数据。断轴图中不可见的区间应标记为插值段，而不是直接观测数据。

安装方
法将整个文件夹复制到 Codex skills 目录：C:\Users\<你的用户名>\.codex\skills\scientific-plot-digitizer

重启 Codex 后在对话框中输入$scientific-plot-digitizer即可使用
