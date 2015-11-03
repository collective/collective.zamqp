with import <nixpkgs> {};
let dependencies = with pythonPackages; rec {
  _lxml = lxml.override {
    name = "lxml-3.4.4";
    src = fetchurl {
      url = "https://pypi.python.org/packages/source/l/lxml/lxml-3.4.4.tar.gz";
      md5 = "a9a65972afc173ec7a39c585f4eea69c";
    };
  };
  _pillow = pillow.override {
    name = "Pillow-2.7.0";
    src = fetchurl {
      url = "https://pypi.python.org/packages/source/P/Pillow/Pillow-2.7.0.zip";
      md5 = "da10ee9d0c0712c942224300c2931a1a";
    };
  };
};
in with dependencies;
stdenv.mkDerivation rec {
  name = "buildout";
  env = buildEnv { name = name; paths = buildInputs; };
  builder = builtins.toFile "builder.sh" ''
    source $stdenv/setup; ln -s $env $out
  '';
  buildInputs = [
    rabbitmq_server
    (pythonPackages.zc_buildout_nix.overrideDerivation (args: {
      postInstall = "";
      propagatedNativeBuildInputs = [
        pythonPackages.readline
        _lxml
        _pillow
      ];
    }))
  ];
}
