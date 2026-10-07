# 字体测试夹具

`lyrics-test.ttf` 是本项目自行生成的测试字体，字体家族为 `Floating Lyrics Test`；`lyrics-test.ttc` 含该家族及 `Floating Lyrics Second`；`lyrics-test.otf` 为 CFF 轮廓的 `Floating Lyrics OpenType`。三者采用 CC0 1.0 公共领域贡献。字形只是矩形，用于验证真实字体加载、复制、持久化、缺字回退和超出字宽／升部的布局，不是供用户使用的字体。

无需额外测试或运行时依赖即可使用已提交的 TTF/TTC/OTF。开发者可通过 `tools/make_test_font.py` 重建它；仅重建工具需要 fontTools。该字体不作为内置字体打入程序资源；验证可将它导入隔离的测试目录。夹具不包含 Windows 字体文件。
