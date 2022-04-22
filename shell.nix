{ pkgs ? import <nixpkgs> {} }:

with pkgs;

stdenv.mkDerivation {
  name = "dev-shell";
  nativeBuildInputs = [ python38 foreman ];

  dontAddPythonPath = "1";
  SOURCE_DATE_EPOCH = "315532800";
  
  shellHook = lib.optionalString stdenv.isLinux ''
    # fixes libstdc++ issues and libgl.so issues
    export LD_LIBRARY_PATH="${stdenv.cc.cc.lib}/lib"
  '';
}
