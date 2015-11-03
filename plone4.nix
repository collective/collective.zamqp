with import <nixpkgs> {};
let dependencies = with pythonPackages; rec {
  _lxml = lxml.override {
    name = "lxml-2.3.6";
    src = fetchurl {
      url = "https://pypi.python.org/packages/source/l/lxml/lxml-2.3.6.tar.gz";
      md5 = "d5d886088e78b1bdbfd66d328fc2d0bc";
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
  name = "env";
  env = buildEnv { name = name; paths = buildInputs; };
  builder = builtins.toFile "builder.pl" ''
    source $stdenv/setup; ln -s $env $out
  '';
  buildInputs = [
    rabbitmq_server
    (pythonPackages.zc_buildout_nix.overrideDerivation(args: {
      postInstall = "";
      propagatedNativeBuildInputs = [
        pythonPackages.readline
        _lxml
        _pillow
      ];
    }))
  ];
  shellHook = ''
    export SSL_CERT_FILE=${cacert}/etc/ssl/certs/ca-bundle.crt
  '';
}
