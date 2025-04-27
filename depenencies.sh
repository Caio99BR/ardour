#!/bin/bash

pacman -S --noconfirm \
    mingw-w64-x86_64-gcc \
    mingw-w64-x86_64-make \
    mingw-w64-x86_64-python \
    mingw-w64-x86_64-vamp-plugin-sdk \
    mingw-w64-x86_64-rubberband \
    mingw-w64-x86_64-jack2 \
    mingw-w64-x86_64-gtkmm \
    mingw-w64-x86_64-boost \
    mingw-w64-x86_64-lilv \
    mingw-w64-x86_64-libjpeg-turbo \
    mingw-w64-x86_64-pkg-config \
    mingw-w64-x86_64-curl \
    mingw-w64-x86_64-libarchive \
    mingw-w64-x86_64-liblo \
    mingw-w64-x86_64-taglib \
    mingw-w64-x86_64-libusb \
    mingw-w64-x86_64-drmingw \
    mingw-w64-x86_64-aubio \
    mingw-w64-x86_64-flac \
    mingw-w64-x86_64-cppunit \
    mingw-w64-x86_64-suil \
    mingw-w64-x86_64-libwebsockets \
    make \
    rsync\
    git

pacman -S --noconfirm \
    mingw-w64-x86_64-aubio \
    mingw-w64-x86_64-binutils \
    mingw-w64-x86_64-boost \
    mingw-w64-x86_64-boost-libs \
    mingw-w64-x86_64-cairo \
    mingw-w64-x86_64-cairomm \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-cppunit \
    mingw-w64-x86_64-curl \
    mingw-w64-x86_64-drmingw \
    mingw-w64-x86_64-expat \
    mingw-w64-x86_64-fftw \
    mingw-w64-x86_64-flac \
    mingw-w64-x86_64-fontconfig \
    mingw-w64-x86_64-freetype \
    mingw-w64-x86_64-fribidi \
    mingw-w64-x86_64-gettext-libtextstyle \
    mingw-w64-x86_64-gettext-runtime \
    mingw-w64-x86_64-gettext-tools \
    mingw-w64-x86_64-glib2 \
    mingw-w64-x86_64-glibmm \
    mingw-w64-x86_64-gnome-common \
    mingw-w64-x86_64-gobject-introspection \
    mingw-w64-x86_64-harfbuzz \
    mingw-w64-x86_64-itstool \
    mingw-w64-x86_64-jack2 \
    mingw-w64-x86_64-gtk3 \
    mingw-w64-x86_64-gtk-doc \
    mingw-w64-x86_64-libusb \
    mingw-w64-x86_64-libarchive \
    mingw-w64-x86_64-libffi \
    mingw-w64-x86_64-libtiff \
    mingw-w64-x86_64-libmariadbclient \
    mingw-w64-x86_64-libwebsockets \
    mingw-w64-x86_64-lilv \
    mingw-w64-x86_64-perl \
    mingw-w64-x86_64-pangomm \
    mingw-w64-x86_64-postgresql \
    mingw-w64-x86_64-portaudio \
    mingw-w64-x86_64-python \
    mingw-w64-x86_64-python-beautifulsoup4 \
    mingw-w64-x86_64-python-requests \
    mingw-w64-x86_64-python-rdflib \
    mingw-w64-x86_64-readline \
    mingw-w64-x86_64-rubberband \
    mingw-w64-x86_64-sratom \
    mingw-w64-x86_64-serd \
    mingw-w64-x86_64-sord \
    mingw-w64-x86_64-taglib \
    mingw-w64-x86_64-toolchain \
    mingw-w64-x86_64-vamp-plugin-sdk \
    mingw-w64-x86_64-xz \
    mingw-w64-x86_64-yajl \
    mingw-w64-x86_64-yelp-tools \
    mingw-w64-x86_64-zlib
pacman -S mingw-w64-x86_64-asio

pacman -S --noconfirm \
    mingw-w64-x86_64-raptor \
    mingw-w64-x86_64-rasqal \
    mingw-w64-x86_64-redland

git config --local user.email "Caio99BR@DraVee"
git config --local user.name "CI Runner"

git clone https://github.com/Caio99BR/ardour

cd ardour/

git tag -a "9.0-unnoficial" -m "Dummy tag for CI"

