# Stack IPA

Combines a Spotify IPA you supply with the EeveeSpotify and Chroma tweak packages you supply. Runs entirely in the browser (Python through Pyodide) or from the command line. No Spotify, Eevee or Chroma files are included here.

## Web page

Settings, Pages, Source: Deploy from a branch, pick this branch and the `/docs` folder. Open the published page, choose the three files, tap Check files, then Build IPA, then Download IPA. Sign the result with your usual sideloading tool.

## Command line

    cd docs
    python3 -m stackipa --ipa Spotify.ipa --eevee eevee.deb --chroma chroma.deb -o stacked.ipa

Either tweak can be given alone for a staged test. `--dry-run` checks everything without writing the IPA.

## Tests

    python3 -m unittest discover -s tests

## Notes

- The IPA must be decrypted and the main executable thin arm64.
- Chroma builds name the Spotify versions they were made for; a mismatch stops the build unless forced.
- The sideload keychain and App Group fix that Eevee's own workflow adds is not included, and neither is Chroma's Live Activity extension.
- Orion and CydiaSubstrate frameworks are downloaded from the pinned pyzule-rw commit and checked against SHA-256 hashes.
