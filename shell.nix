{ pkgs ? import <nixpkgs> { } }:

let
  pythonEnv = pkgs.python3.withPackages (ps: [
    ps.pyqt5
    ps.pillow
  ]);
in
pkgs.mkShell {
  name = "palletteffy";

  packages = [
    pythonEnv
    pkgs.qt5.qtbase
    pkgs.qt5.qtwayland
    pkgs.libsForQt5.qt5ct
    pkgs.libGL
  ];

  shellHook = ''
    # Use this shell's Qt5 plugins, but keep the desktop's platform theme
    # (qt5ct / KDE / GTK) so widget style, fonts, and colours come from
    # the system Qt5 settings.
    export QT_PLUGIN_PATH="${pkgs.qt5.qtbase}/${pkgs.qt5.qtbase.qtPluginPrefix}"
    export QML2_IMPORT_PATH="${pkgs.qt5.qtbase}/${pkgs.qt5.qtbase.qtQmlPrefix}"
    if [ -z "$QT_QPA_PLATFORMTHEME" ]; then
      export QT_QPA_PLATFORMTHEME=qt5ct
    fi
    echo "Palletteffy shell ready (PyQt5, system theme via \$QT_QPA_PLATFORMTHEME)."
    echo "Run:  python palletteffy.py"
  '';
}
