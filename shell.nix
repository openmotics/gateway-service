{ pkgs ? import <nixpkgs> {} }:

with pkgs;

stdenv.mkDerivation {
  name = "dev-shell";
  nativeBuildInputs = [ python38 foreman ];

  dontAddPythonPath = "1";
  SOURCE_DATE_EPOCH = "315532800";
}
