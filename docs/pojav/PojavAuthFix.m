#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

typedef void (^PAFStatusBlock)(id status, BOOL success);
typedef void (^PAFXSTSBlock)(NSString *xsts, NSString *uhs);

static BOOL gReportHooked = NO;
static BOOL gXboxHooked = NO;
static BOOL gAnnounced = NO;

static NSString *PAFDescribe(NSError *error) {
    NSMutableArray *lines = [NSMutableArray arrayWithObject:error.localizedDescription ?: @"Unknown error"];
    NSURL *url = error.userInfo[NSURLErrorFailingURLErrorKey];
    if ([url isKindOfClass:NSURL.class]) {
        NSURLComponents *parts = [NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO];
        parts.query = nil;
        [lines addObject:parts.URL.absoluteString ?: (url.host ?: @"")];
    }
    NSHTTPURLResponse *response = error.userInfo[@"com.alamofire.serialization.response.error.response"];
    if ([response isKindOfClass:NSHTTPURLResponse.class]) {
        [lines addObject:[NSString stringWithFormat:@"HTTP %ld", (long)response.statusCode]];
    }
    NSData *data = error.userInfo[@"com.alamofire.serialization.response.error.data"];
    if ([data isKindOfClass:NSData.class] && data.length > 0) {
        NSString *body = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        if (body.length > 700) {
            body = [body substringToIndex:700];
        }
        if (body) {
            [lines addObject:body];
        }
    }
    NSError *underlying = error.userInfo[NSUnderlyingErrorKey];
    if ([underlying isKindOfClass:NSError.class]) {
        [lines addObject:underlying.localizedDescription ?: @""];
    }
    return [lines componentsJoinedByString:@"\n"];
}

static UIViewController *PAFTopViewController(void) {
    UIWindow *window = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class]) {
            continue;
        }
        for (UIWindow *candidate in ((UIWindowScene *)scene).windows) {
            if (candidate.isKeyWindow) {
                window = candidate;
            }
        }
    }
    if (window == nil) {
        window = UIApplication.sharedApplication.windows.firstObject;
    }
    UIViewController *top = window.rootViewController;
    while (top.presentedViewController) {
        top = top.presentedViewController;
    }
    return top;
}

static void PAFPresentTitled(NSString *title, NSString *text) {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIViewController *top = PAFTopViewController();
        if (top == nil) {
            UIPasteboard.generalPasteboard.string = [NSString stringWithFormat:@"%@\n%@", title, text];
            return;
        }
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:title
                                                                       message:text
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"Copy" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
            UIPasteboard.generalPasteboard.string = text;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleCancel handler:nil]];
        [top presentViewController:alert animated:YES completion:nil];
    });
}

static void PAFPresent(NSString *text) {
    PAFPresentTitled(@"Sign-in failed", text);
}

static BOOL PAFHookFailureReport(void) {
    Class cls = objc_getClass("AccountListViewController");
    SEL selector = NSSelectorFromString(@"callbackMicrosoftAuth:success:forCell:");
    Method method = cls ? class_getInstanceMethod(cls, selector) : NULL;
    if (method == NULL) {
        return NO;
    }
    IMP original = method_getImplementation(method);
    IMP replacement = imp_implementationWithBlock(^(id self, id status, BOOL success, id cell) {
        if (!success && [status isKindOfClass:NSError.class]) {
            PAFPresent(PAFDescribe(status));
        }
        ((void (*)(id, SEL, id, BOOL, id))original)(self, selector, status, success, cell);
    });
    method_setImplementation(method, replacement);
    return YES;
}

static BOOL PAFHookXboxProfile(void) {
    Class cls = objc_getClass("MicrosoftAuthenticator");
    if (cls == nil) {
        return NO;
    }
    SEL profileSelector = NSSelectorFromString(@"acquireXboxProfile:xstsToken:callback:");
    Method profile = class_getInstanceMethod(cls, profileSelector);
    SEL xstsSelector = NSSelectorFromString(@"acquireXSTSFor:token:xstsCallback:callback:");
    Method xsts = class_getInstanceMethod(cls, xstsSelector);
    if (profile == NULL || xsts == NULL) {
        return NO;
    }
    method_setImplementation(profile, imp_implementationWithBlock(^(id self, NSString *uhs, NSString *token, PAFStatusBlock callback) {
        callback(nil, YES);
    }));
    IMP original = method_getImplementation(xsts);
    method_setImplementation(xsts, imp_implementationWithBlock(^(id self, NSString *party, NSString *token, PAFXSTSBlock xstsCallback, PAFStatusBlock callback) {
        if ([party hasPrefix:@"http://xboxlive.com"]) {
            xstsCallback(@"skipped", @"skipped");
            return;
        }
        ((void (*)(id, SEL, id, id, id, id))original)(self, xstsSelector, party, token, xstsCallback, callback);
    }));
    return YES;
}

static void PAFInstall(void) {
    if (!gReportHooked) {
        gReportHooked = PAFHookFailureReport();
    }
    if (!gXboxHooked) {
        gXboxHooked = PAFHookXboxProfile();
    }
}

static void PAFAnnounce(void) {
    if (gAnnounced) {
        return;
    }
    gAnnounced = YES;
    NSString *text = [NSString stringWithFormat:@"Library loaded.\nFailure report hook: %@\nXbox skip hook: %@",
                      gReportHooked ? @"on" : @"missing", gXboxHooked ? @"on" : @"missing"];
    PAFPresentTitled(@"PojavAuthFix", text);
}

static void PAFRetry(int attempt) {
    PAFInstall();
    if ((gReportHooked && gXboxHooked) || attempt >= 10) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            PAFAnnounce();
        });
        return;
    }
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(NSEC_PER_SEC / 2)), dispatch_get_main_queue(), ^{
        PAFRetry(attempt + 1);
    });
}

__attribute__((constructor)) static void PAFInit(void) {
    PAFInstall();
    dispatch_async(dispatch_get_main_queue(), ^{
        PAFRetry(0);
    });
}
