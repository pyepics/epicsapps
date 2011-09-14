installdir='/www/apache/htdocs/software/python/pyepicsapps'
docbuild='doc/_build'
appname='epicsapps'
dockit=$appname_docs.tgz

cd doc 
echo '# Making docs'
make all
cd ../

echo '# Building tarball of docs'
mkdir _tmpdoc
cp -pr doc/$appname.pdf     _tmpdoc/.
cp -pr doc/_build/html/*    _tmpdoc/.
cd _tmpdoc
tar czf ../../$dockit .
cd ..
rm -rf _tmpdoc 

# 

echo "# Switching to gh-pages branch"
git checkout gh-pages

if  [ $? -ne 0 ]  ; then 
  echo ' failed.'
  exit 
fi

echo "# Make sure this script is updated!"
git checkout master publish_docs.sh
if  [ $? -ne 0 ]  ; then 
  echo ' failed.'
  exit 
fi

tar xzf ../$dockit .

echo "# commit changes to gh-pages branch"
echo '##  git commit -am "changed docs" '

if  [ $? -ne 0 ]  ; then 
  echo ' failed.'
  exit 
fi

echo "# Pushing docs to github"
echo '## git push '


echo "# switch back to master branch"
git checkout master

if  [ $? -ne 0 ]  ; then 
  echo ' failed.'
  exit 
fi

# install locally
echo "# Installing docs to CARS web pages"
echo '## cp ../$dockit  $installdir/../. '

cd $installdir
if  [ $? -ne 0 ]  ; then 
  echo ' failed.'
  exit 
fi

tar xvf ../$dockit .
